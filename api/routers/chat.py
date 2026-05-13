"""Chat endpoints: sync POST and streaming WebSocket."""

import json
import logging
import os
import time
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from api.auth import get_current_payload, get_tenant_id
from api.schemas import QueryRequest, QueryResponse, CitationSource

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


def _get_tenant_slug(tenant_id: str) -> str:
    import psycopg2
    conn = psycopg2.connect(POSTGRES_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Tenant not found: {tenant_id}")
            return row[0]
    finally:
        conn.close()


@router.post("", response_model=QueryResponse)
async def chat(body: QueryRequest, tenant_id: str = Depends(get_tenant_id)):
    """Synchronous RAG query. Returns full answer with citations."""
    t_start = time.monotonic()

    tenant_slug = _get_tenant_slug(tenant_id)

    from retrieval.hybrid import HybridRetriever
    from generation.prompt import build_prompt
    from generation.llm import generate, is_available
    from generation.citations import extract_citations

    chunks = HybridRetriever().retrieve(body.query, tenant_slug, final_k=body.top_k)

    if not chunks:
        return QueryResponse(
            answer="Sorunuzla ilgili belge bulunamadı. Lütfen önce belge yükleyin.",
            citations=[],
            query_time_ms=int((time.monotonic() - t_start) * 1000),
            tenant_id=tenant_id,
        )

    if not is_available():
        return QueryResponse(
            answer="LLM modeli mevcut değil. Lütfen model dosyasını indirin.",
            citations=[],
            query_time_ms=int((time.monotonic() - t_start) * 1000),
            tenant_id=tenant_id,
        )

    prompt = build_prompt(body.query, chunks)
    answer = generate(prompt)
    from generation.citations import strip_think_tags
    answer = strip_think_tags(answer)
    raw_citations = extract_citations(answer, chunks)
    citations = [CitationSource(**c) for c in raw_citations]

    query_time_ms = int((time.monotonic() - t_start) * 1000)
    logger.info("Chat query answered in %d ms for tenant %s", query_time_ms, tenant_id)

    return QueryResponse(
        answer=answer,
        citations=citations,
        query_time_ms=query_time_ms,
        tenant_id=tenant_id,
    )


@router.websocket("/stream")
async def chat_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming RAG responses token by token.

    Client sends: {"query": "...", "token": "<jwt>", "top_k": 5}
    Server sends: token frames, then a 'done' frame.
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

    # Authenticate via token in message
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

    from generation.streamer import stream_rag_response
    await stream_rag_response(websocket, query, tenant_slug, top_k=top_k)

    try:
        await websocket.close()
    except Exception:
        pass
