"""Chat endpoints: sync POST and streaming WebSocket."""

import contextlib
import json
import logging
import time

from fastapi import APIRouter, Depends, WebSocket

from api.auth import get_tenant_id
from api.db import get_conn
from api.schemas import CitationSource, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

HISTORY_LIMIT = 8  # max messages (4 turns) loaded from DB per request


def _get_tenant_slug(tenant_id: str) -> str:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Tenant not found: {tenant_id}")
            return row[0]
    finally:
        conn.close()


def _get_or_create_session(tenant_id: str, session_id, user_id: str = "demo-user") -> str:
    """Return existing session UUID or create a new one."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            if session_id:
                cur.execute(
                    "SELECT id FROM sessions WHERE id=%s AND tenant_id=%s",
                    (session_id, tenant_id),
                )
                row = cur.fetchone()
                if row:
                    return str(row[0])
            cur.execute(
                "INSERT INTO sessions (tenant_id, user_id) VALUES (%s, %s) RETURNING id",
                (tenant_id, user_id),
            )
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _load_history(session_id: str) -> list:
    """Load the last HISTORY_LIMIT messages for a session, oldest-first."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, created_at
                    FROM messages WHERE session_id=%s
                    ORDER BY created_at DESC LIMIT %s
                ) sub ORDER BY created_at ASC
                """,
                (session_id, HISTORY_LIMIT),
            )
            return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def _save_messages(session_id: str, user_text: str, assistant_text: str, citations: list):
    """Persist the user question and assistant answer to the messages table."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (session_id, role, content, citations) VALUES "
                "(%s, %s, %s, %s), (%s, %s, %s, %s)",
                (
                    session_id, "user", user_text, json.dumps([]),
                    session_id, "assistant", assistant_text, json.dumps(citations),
                ),
            )
    finally:
        conn.close()


def _log_query(tenant_id: str, session_id: str, query: str,
               answer_length: int, num_citations: int, query_time_ms: int):
    """Write a query analytics record."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO query_logs
                       (tenant_id, session_id, query, answer_length, num_citations, query_time_ms)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                (tenant_id, session_id, query, answer_length, num_citations, query_time_ms),
            )
    except Exception as exc:
        logger.warning("Failed to write query log: %s", exc)
    finally:
        conn.close()


@router.post("", response_model=QueryResponse)
async def chat(body: QueryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Synchronous RAG query. Returns full answer with citations."""
    t_start = time.monotonic()

    tenant_slug = _get_tenant_slug(tenant_id)
    session_id = _get_or_create_session(tenant_id, body.session_id)
    history = _load_history(session_id)

    from generation.citations import extract_citations, strip_think_tags
    from generation.llm import generate, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    chunks = HybridRetriever().retrieve(body.query, tenant_slug, final_k=body.top_k)

    if not chunks:
        return QueryResponse(
            answer="Sorunuzla ilgili belge bulunamadı. Lütfen önce belge yükleyin.",
            citations=[],
            query_time_ms=int((time.monotonic() - t_start) * 1000),
            tenant_id=tenant_id,
            session_id=session_id,
        )

    if not is_available():
        return QueryResponse(
            answer="LLM modeli mevcut değil. Lütfen model dosyasını indirin.",
            citations=[],
            query_time_ms=int((time.monotonic() - t_start) * 1000),
            tenant_id=tenant_id,
            session_id=session_id,
        )

    prompt = build_prompt(body.query, chunks, history=history)
    answer = strip_think_tags(generate(prompt))
    raw_citations = extract_citations(answer, chunks)
    citations = [CitationSource(**c) for c in raw_citations]

    query_time_ms = int((time.monotonic() - t_start) * 1000)
    logger.info("Chat query answered in %d ms for tenant %s", query_time_ms, tenant_id)

    _save_messages(session_id, body.query, answer, raw_citations)
    _log_query(tenant_id, session_id, body.query, len(answer), len(citations), query_time_ms)

    return QueryResponse(
        answer=answer,
        citations=citations,
        query_time_ms=query_time_ms,
        tenant_id=tenant_id,
        session_id=session_id,
    )


@router.websocket("/stream")
async def chat_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming RAG responses token by token.

    Client sends: {"query": "...", "token": "<jwt>", "session_id": "<uuid|null>", "top_k": 5}
    Server sends: token frames, then a 'done' frame with session_id + citations.
    """
    await websocket.accept()
    logger.info("WebSocket connection opened")

    try:
        data = await websocket.receive_text()
        payload_json = json.loads(data)
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": f"Invalid message: {exc}"}))
        await websocket.close()
        return

    from api.auth import decode_token
    token = payload_json.get("token", "")
    try:
        claims = decode_token(token)
        tenant_id = claims["tenant_id"]
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": f"Auth failed: {exc}"}))
        await websocket.close()
        return

    query = payload_json.get("query", "").strip()
    top_k = int(payload_json.get("top_k", 5))
    client_session_id = payload_json.get("session_id")

    if not query:
        await websocket.send_text(json.dumps({"type": "error", "message": "Empty query"}))
        await websocket.close()
        return

    try:
        tenant_slug = _get_tenant_slug(tenant_id)
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await websocket.close()
        return

    session_id = _get_or_create_session(tenant_id, client_session_id)
    history = _load_history(session_id)

    from generation.streamer import stream_rag_response
    result = await stream_rag_response(
        websocket, query, tenant_slug, top_k=top_k,
        history=history, session_id=session_id,
    )

    if result:
        _save_messages(session_id, query, result["text"], result["citations"])
        _log_query(
            tenant_id, session_id, query,
            len(result["text"]), len(result["citations"]),
            result.get("query_time_ms", 0),
        )

    with contextlib.suppress(Exception):
        await websocket.close()
