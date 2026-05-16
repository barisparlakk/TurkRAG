"""TurkRAG FastAPI application entrypoint.

On startup: initialise PostgreSQL schema and ensure upload/index directories exist.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.auth import create_token
from api.middleware import setup_middleware
from api.routers import analytics, chat, documents, health, sessions, tenants

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads"))
BM25_INDEX_DIR = Path(os.getenv("BM25_INDEX_DIR", "indexes"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks and yield to serve requests."""
    logger.info("TurkRAG API starting up…")
    if os.getenv("JWT_SECRET", "change_this_in_production") == "change_this_in_production":
        logger.warning(
            "JWT_SECRET is the default insecure value. "
            "Set JWT_SECRET env var before deploying to production."
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _init_postgres()
    logger.info("Startup complete. Ready to serve.")
    yield
    logger.info("TurkRAG API shutting down.")


def _init_postgres():
    """Create database schema if tables do not exist."""
    import psycopg2

    logger.info("Initialising PostgreSQL schema…")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
    except Exception as exc:
        logger.error("Failed to connect to PostgreSQL: %s", exc)
        logger.error("Ensure PostgreSQL is running and POSTGRES_URL is correct.")
        return

    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS tenants (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT NOT NULL UNIQUE,
                        slug TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS documents (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                        filename TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        chunk_count INTEGER,
                        status TEXT DEFAULT 'processing',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                        email TEXT NOT NULL,
                        role TEXT DEFAULT 'member',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS sessions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL DEFAULT 'anonymous',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        citations JSONB DEFAULT '[]',
                        feedback SMALLINT DEFAULT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS query_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
                        query TEXT NOT NULL,
                        answer_length INT,
                        num_citations INT,
                        query_time_ms INT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback SMALLINT DEFAULT NULL;

                    CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON sessions(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                    CREATE INDEX IF NOT EXISTS idx_query_logs_tenant ON query_logs(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
                """)
        logger.info("PostgreSQL schema ready.")
    except Exception as exc:
        logger.error("Failed to initialise PostgreSQL schema: %s", exc)
    finally:
        conn.close()


# Rate limiter (per IP; production should key on tenant_id)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="TurkRAG API",
    description="Privacy-first, on-premise RAG for Turkish enterprise",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

setup_middleware(app)

# Routers
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(tenants.router)
app.include_router(analytics.router)
app.include_router(sessions.router)


# Simple token creation endpoint (dev convenience — replace with proper auth in production)
@app.post("/auth/token", tags=["auth"])
async def get_token(request: Request):
    """Issue a JWT for dev/testing. Body: {tenant_id, user_id, role}."""
    body = await request.json()
    token = create_token(
        tenant_id=body.get("tenant_id", ""),
        user_id=body.get("user_id", ""),
        role=body.get("role", "member"),
    )
    return {"access_token": token, "token_type": "bearer"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
