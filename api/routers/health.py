"""Health check and model status endpoints."""

import logging
import os

from fastapi import APIRouter

from api.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return health status of all dependencies."""
    qdrant_status = "ok"
    postgres_status = "ok"

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url, timeout=3)
        client.get_collections()
    except Exception as exc:
        qdrant_status = f"error: {exc}"
        logger.warning("Qdrant health check failed: %s", exc)

    # Check PostgreSQL
    try:
        import psycopg2
        postgres_url = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
        conn = psycopg2.connect(postgres_url, connect_timeout=3)
        conn.close()
    except Exception as exc:
        postgres_status = f"error: {exc}"
        logger.warning("PostgreSQL health check failed: %s", exc)

    # Check LLM
    from generation.llm import is_available
    llm_ok = is_available()

    overall = "ok" if qdrant_status == "ok" and postgres_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        qdrant=qdrant_status,
        postgres=postgres_status,
        llm_available=llm_ok,
    )
