"""WebSocket token streamer for the RAG chat endpoint.

Frame protocol:
  {"type": "token",   "content": "<token_text>"}
  {"type": "done",    "citations": [...], "query_time_ms": 340}
  {"type": "error",   "message": "<error description>"}
"""

import json
import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def stream_rag_response(
    websocket,
    query: str,
    tenant_slug: str,
    top_k: int = 5,
) -> None:
    """Run full RAG pipeline and stream tokens over a WebSocket connection.

    Sends token frames during generation, then a final 'done' frame with citations.
    """
    from retrieval.hybrid import HybridRetriever
    from generation.prompt import build_prompt
    from generation.llm import generate_stream, is_available
    from generation.citations import extract_citations

    t_start = time.monotonic()

    async def send(frame: Dict[str, Any]):
        await websocket.send_text(json.dumps(frame, ensure_ascii=False))

    try:
        # Retrieval
        logger.info("WS RAG: query='%s...' tenant=%s", query[:50], tenant_slug)
        retriever = HybridRetriever()
        chunks = retriever.retrieve(query, tenant_slug, final_k=top_k)

        if not chunks:
            await send({"type": "error", "message": "İlgili belge bulunamadı. Lütfen önce belge yükleyin."})
            return

        # Build prompt
        prompt = build_prompt(query, chunks)

        # Check LLM availability
        if not is_available():
            await send({
                "type": "error",
                "message": "LLM modeli yüklenmemiş. Lütfen modeli indirin ve sunucuyu yeniden başlatın.",
            })
            return

        # Stream tokens
        full_response = []
        for token in generate_stream(prompt):
            full_response.append(token)
            await send({"type": "token", "content": token})

        from generation.citations import strip_think_tags
        response_text = strip_think_tags("".join(full_response))
        citations = extract_citations(response_text, chunks)
        query_time_ms = int((time.monotonic() - t_start) * 1000)

        await send({
            "type": "done",
            "citations": citations,
            "query_time_ms": query_time_ms,
        })
        logger.info("WS stream complete: %d tokens, %d ms", len(full_response), query_time_ms)

    except Exception as exc:
        logger.exception("Error during WS RAG streaming: %s", exc)
        await send({"type": "error", "message": str(exc)})
