"""Export endpoints: session export and analytics report."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from api.auth import get_current_user
from api.db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


@router.get("/sessions/{session_id}/txt")
async def export_session_txt(session_id: str, user: dict = Depends(get_current_user)):
    """Export a chat session as plain text."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            params = [session_id, user["tenant_id"]]
            owner_filter = ""
            if user.get("role") != "admin":
                owner_filter = "AND s.user_id = %s"
                params.append(user["id"])
            cur.execute(
                f"""SELECT s.id FROM sessions s
                   WHERE s.id=%s AND s.tenant_id=%s {owner_filter}""",
                tuple(params),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Session not found")

            cur.execute(
                """SELECT role, content, created_at FROM messages
                   WHERE session_id=%s ORDER BY created_at ASC""",
                (session_id,),
            )
            messages = cur.fetchall()
    finally:
        conn.close()

    lines = [f"TurkRAG Chat Export - Session {session_id}", "=" * 50, ""]
    for role, content, ts in messages:
        label = "Kullanıcı" if role == "user" else "Asistan"
        lines.append(f"[{ts}] {label}:")
        lines.append(content)
        lines.append("")

    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="session_{session_id[:8]}.txt"'},
    )


@router.get("/sessions/{session_id}/json")
async def export_session_json(session_id: str, user: dict = Depends(get_current_user)):
    """Export a chat session as JSON."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            params = [session_id, user["tenant_id"]]
            owner_filter = ""
            if user.get("role") != "admin":
                owner_filter = "AND user_id = %s"
                params.append(user["id"])
            cur.execute(
                f"SELECT id FROM sessions WHERE id=%s AND tenant_id=%s {owner_filter}",
                tuple(params),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Session not found")

            cur.execute(
                """SELECT role, content, citations, created_at FROM messages
                   WHERE session_id=%s ORDER BY created_at ASC""",
                (session_id,),
            )
            messages = cur.fetchall()
    finally:
        conn.close()

    data = {
        "session_id": session_id,
        "messages": [
            {
                "role": r[0],
                "content": r[1],
                "citations": json.loads(r[2]) if r[2] else [],
                "timestamp": str(r[3]),
            }
            for r in messages
        ],
    }
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="session_{session_id[:8]}.json"'},
    )


@router.get("/analytics/report")
async def export_analytics_report(user: dict = Depends(get_current_user)):
    """Summary report: query stats, response times, feedback."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*), AVG(query_time_ms), MAX(query_time_ms),
                          AVG(num_citations), AVG(answer_length)
                   FROM query_logs WHERE tenant_id=%s""",
                (user["tenant_id"],),
            )
            row = cur.fetchone()
            total_queries = row[0] or 0
            avg_time = round(float(row[1]), 1) if row[1] else 0
            max_time = row[2] or 0
            avg_citations = round(float(row[3]), 1) if row[3] else 0
            avg_answer_len = round(float(row[4]), 1) if row[4] else 0

            cur.execute(
                """SELECT feedback, COUNT(*) FROM messages
                   WHERE session_id IN (SELECT id FROM sessions WHERE tenant_id=%s)
                   AND feedback IS NOT NULL
                   GROUP BY feedback""",
                (user["tenant_id"],),
            )
            feedback = {str(r[0]): r[1] for r in cur.fetchall()}

            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE tenant_id=%s AND status='ready'",
                (user["tenant_id"],),
            )
            doc_count = cur.fetchone()[0] or 0
    finally:
        conn.close()

    return {
        "tenant_id": user["tenant_id"],
        "total_queries": total_queries,
        "avg_response_time_ms": avg_time,
        "max_response_time_ms": max_time,
        "avg_citations_per_query": avg_citations,
        "avg_answer_length": avg_answer_len,
        "feedback_distribution": feedback,
        "total_documents": doc_count,
    }
