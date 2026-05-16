"""Session history and message feedback endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_tenant_id
from api.db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(limit: int = 30, tenant_id: str = Depends(get_tenant_id)):
    """Return recent sessions for the tenant, newest first.

    Each entry includes a preview (first user message truncated to 80 chars)
    and the total message count so the UI can show a meaningful label.
    """
    limit = min(max(limit, 1), 100)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.created_at,
                    COUNT(m.id)                                    AS message_count,
                    MIN(m.content) FILTER (WHERE m.role = 'user') AS preview
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.tenant_id = %s
                GROUP BY s.id
                ORDER BY s.created_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(r[0]),
            "created_at": str(r[1]),
            "message_count": r[2],
            "preview": (r[3] or "")[:80] if r[3] else "Boş oturum",
        }
        for r in rows
    ]


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, tenant_id: str = Depends(get_tenant_id)):
    """Return all messages in a session, oldest first.

    Verifies the session belongs to the requesting tenant.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Ownership check
            cur.execute(
                "SELECT id FROM sessions WHERE id=%s AND tenant_id=%s",
                (session_id, tenant_id),
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
    tenant_id: str = Depends(get_tenant_id),
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
            cur.execute(
                """SELECT m.id FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE m.id=%s AND m.role='assistant' AND s.tenant_id=%s""",
                (message_id, tenant_id),
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
