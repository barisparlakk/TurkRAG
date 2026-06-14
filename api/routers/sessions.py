"""Session history and message feedback endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(limit: int = 30, user: dict = Depends(get_current_user)):
    """Return recent sessions for the tenant, newest first.

    Each entry includes a preview (first user message truncated to 80 chars)
    and the total message count so the UI can show a meaningful label.
    """
    limit = min(max(limit, 1), 100)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            params = [user["tenant_id"]]
            owner_filter = ""
            if user.get("role") != "admin":
                owner_filter = "AND s.user_id = %s"
                params.append(user["id"])
            params.append(limit)
            cur.execute(
                f"""
                SELECT
                    s.id,
                    s.created_at,
                    s.user_id,
                    COUNT(m.id)                                    AS message_count,
                    MIN(m.content) FILTER (WHERE m.role = 'user') AS preview
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.tenant_id = %s {owner_filter}
                GROUP BY s.id
                ORDER BY s.created_at DESC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(r[0]),
            "created_at": str(r[1]),
            "user_id": r[2],
            "message_count": r[3],
            "preview": (r[4] or "")[:80] if r[4] else "Boş oturum",
        }
        for r in rows
    ]


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, user: dict = Depends(get_current_user)):
    """Return all messages in a session, oldest first.

    Verifies the session belongs to the requesting tenant.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Ownership check
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
                """SELECT id, role, content, citations, feedback, created_at
                   FROM messages WHERE session_id=%s ORDER BY created_at ASC""",
                (session_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(r[0]),
            "role": r[1],
            "content": r[2],
            "citations": r[3] or [],
            "feedback": r[4],
            "created_at": str(r[5]),
        }
        for r in rows
    ]


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(
    message_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """Store thumbs-up (1) or thumbs-down (-1) feedback for an assistant message.

    Body: {"value": 1 | -1}
    Only accepts feedback on 'assistant' messages belonging to this tenant.
    """
    value = body.get("value")
    if value not in (1, -1):
        raise HTTPException(status_code=422, detail="value must be 1 or -1")

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            # Verify message exists, is assistant role, and belongs to this tenant
            params = [message_id, user["tenant_id"]]
            owner_filter = ""
            if user.get("role") != "admin":
                owner_filter = "AND s.user_id = %s"
                params.append(user["id"])
            cur.execute(
                f"""SELECT m.id FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE m.id=%s AND m.role='assistant' AND s.tenant_id=%s {owner_filter}""",
                tuple(params),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Message not found")

            cur.execute(
                "UPDATE messages SET feedback=%s WHERE id=%s",
                (value, message_id),
            )
    finally:
        conn.close()

    logger.info("Feedback %+d recorded for message %s", value, message_id)
    return {"status": "ok"}
