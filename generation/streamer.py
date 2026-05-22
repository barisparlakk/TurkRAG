"""WebSocket token streamer for the RAG chat endpoint.

Frame protocol:
  {"type": "token",   "content": "<token_text>"}
  {"type": "done",    "citations": [...], "query_time_ms": 340, "session_id": "<uuid>"}
  {"type": "error",   "message": "<error description>"}
"""

import asyncio
import json
import logging
import queue as stdlib_queue
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


async def stream_rag_response(
    websocket,
    query: str,
    tenant_slug: str,
    top_k: int = 5,
    history: list[dict] | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Run full RAG pipeline and stream tokens over a WebSocket connection.

    Sends token frames during generation, then a final 'done' frame with
    citations and the session_id so the client can continue the conversation.

    Returns a dict {"text", "citations", "query_time_ms"} after streaming
    completes so the caller can persist messages to the DB.
    Returns None if an error occurred before generation.
    """
    from generation.citations import extract_citations, strip_think_tags
    from generation.llm import generate_stream, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    t_start = time.monotonic()

    async def send(frame: dict[str, Any]):
        try:
            await websocket.send_text(json.dumps(frame, ensure_ascii=False))
        except RuntimeError:
            pass  # WebSocket already closed (client disconnected)

    try:
        # Retrieval
        logger.info("WS RAG: query='%s...' tenant=%s", query[:50], tenant_slug)
        retriever = HybridRetriever()
        chunks = retriever.retrieve(query, tenant_slug, final_k=top_k)

        if not chunks:
            await send({"type": "error", "message": "İlgili belge bulunamadı. Lütfen önce belge yükleyin."})
            return None

        # Build prompt — include conversation history if provided
        prompt = build_prompt(query, chunks, history=history)

        # Check LLM availability
        if not is_available():
            await send({
                "type": "error",
                "message": "LLM modeli yüklenmemiş. Lütfen modeli indirin ve sunucuyu yeniden başlatın.",
            })
            return None

        # Stream tokens — run sync generator in a thread to avoid blocking the event loop.
        # cancel_event lets the consumer signal early termination (e.g. client disconnect).
        full_response = []
        token_queue: stdlib_queue.SimpleQueue = stdlib_queue.SimpleQueue()
        cancel_event = threading.Event()

        def _produce():
            try:
                for token in generate_stream(prompt):
                    if cancel_event.is_set():
                        break
                    token_queue.put(token)
            except Exception as exc:
                token_queue.put(exc)
            finally:
                token_queue.put(None)

        threading.Thread(target=_produce, daemon=True).start()
        loop = asyncio.get_running_loop()
        try:
            while True:
                item = await loop.run_in_executor(None, token_queue.get)
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                full_response.append(item)
                await send({"type": "token", "content": item})
        except Exception:
            cancel_event.set()
            raise

        response_text = strip_think_tags("".join(full_response))
        citations = extract_citations(response_text, chunks)
        query_time_ms = int((time.monotonic() - t_start) * 1000)

        await send({
            "type": "done",
            "citations": citations,
            "query_time_ms": query_time_ms,
            "session_id": session_id,
        })
        logger.info("WS stream complete: %d tokens, %d ms", len(full_response), query_time_ms)

        # Attribution — sentence-level source attribution (XAI), sent after done frame
        try:
            from generation.attribution import attribute_answer
            attr_queue: stdlib_queue.SimpleQueue = stdlib_queue.SimpleQueue()

            def _gen_attribution():
                attr_queue.put(attribute_answer(response_text, chunks))

            threading.Thread(target=_gen_attribution, daemon=True).start()
            attr_result = await loop.run_in_executor(None, attr_queue.get)
            if attr_result and attr_result.get("sentences"):
                await send({"type": "attribution", "sentences": attr_result["sentences"]})
        except Exception as exc:
            logger.warning("Could not compute attribution: %s", exc)

        # Generate follow-up questions in a thread (after done frame — no latency to main answer)
        try:
            import os as _os
            if _os.getenv("FOLLOWUP_ENABLED", "true").lower() == "true":
                from generation.followups import generate_followups
                followup_queue: stdlib_queue.SimpleQueue = stdlib_queue.SimpleQueue()

                def _gen_followups():
                    followup_queue.put(generate_followups(query, response_text))

                threading.Thread(target=_gen_followups, daemon=True).start()
                follow_ups = await loop.run_in_executor(None, followup_queue.get)
                if follow_ups:
                    await send({"type": "follow_ups", "questions": follow_ups})
        except Exception as exc:
            logger.warning("Could not send follow-up questions: %s", exc)

        return {"text": response_text, "citations": citations, "query_time_ms": query_time_ms}

    except Exception as exc:
        logger.exception("Error during WS RAG streaming: %s", exc)
        await send({"type": "error", "message": str(exc)})
        return None
