"""Health check and model status endpoints."""

import asyncio
import logging
import os

from fastapi import APIRouter

from api.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


def _check_qdrant() -> str:
    client = None
    try:
        from qdrant_client import QdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url, timeout=3)
        client.get_collections()
        return "ok"
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        return "error"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                logger.warning("Could not close Qdrant health client: %s", exc)


def _check_postgres() -> str:
    try:
        import psycopg2

        postgres_url = os.getenv(
            "POSTGRES_URL",
            "postgresql://turkrag:turkrag_secret@localhost/turkrag",
        )
        conn = psycopg2.connect(postgres_url, connect_timeout=3)
        conn.close()
        return "ok"
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", exc)
        return "error"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return health status of all dependencies."""
    qdrant_status, postgres_status = await asyncio.gather(
        asyncio.to_thread(_check_qdrant),
        asyncio.to_thread(_check_postgres),
    )

    # Check LLM
    from generation.llm import is_available
    llm_ok = is_available()
    overall = "ok" if qdrant_status == "ok" and postgres_status == "ok" else "degraded"
    details = {}
    if os.getenv("HEALTH_INCLUDE_DETAILS", "false").lower() == "true":
        llm_path = os.getenv("LLM_MODEL_PATH", "models/qwen3-8b-instruct-q4_k_m.gguf")
        embedder_path = os.getenv("TURKISH_EMBEDDER_PATH", "models/turkish-embedder")
        details = {
            "llm_model_exists": os.path.exists(llm_path),
            "embedder_exists": os.path.exists(embedder_path),
        }

    return HealthResponse(
        status=overall,
        qdrant=qdrant_status,
        postgres=postgres_status,
        llm_available=llm_ok,
        details=details,
    )
