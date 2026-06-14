"""TurkRAG FastAPI application entrypoint.

On startup: initialise PostgreSQL schema and ensure upload/index directories exist.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.auth import (
    APP_ENV,
    ENABLE_DEV_AUTH,
    create_token,
    require_admin,
    validate_mock_admin,
    verify_password,
)
from api.middleware import setup_middleware
from api.routers import (
    analytics,
    chat,
    documents,
    evaluation,
    export,
    health,
    permissions,
    sessions,
    tenants,
    users,
)
from api.schemas import (
    AdminTenantSwitchRequest,
    DevTokenRequest,
    LoginRequest,
    MockAdminLoginRequest,
)

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
    jwt_secret = os.getenv("JWT_SECRET", "change_this_in_production")
    if APP_ENV == "production" and jwt_secret == "change_this_in_production":
        raise RuntimeError("JWT_SECRET must be set before running in production")
    if jwt_secret == "change_this_in_production":
        logger.warning(
            "JWT_SECRET is the default insecure value. "
            "Set JWT_SECRET env var before deploying to production."
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _init_postgres()
    # Warm up connection pool
    from api.db import _get_pool
    _get_pool()
    # Start background ingestion worker
    from ingestion.worker import start_worker, stop_worker
    start_worker()
    # Eagerly load + warm up LLM in background so first query is fast
    import threading
    def _warmup():
        try:
            from generation.llm import _get_llm
            _get_llm()  # loads model + runs warmup token (see llm.py)
            logger.info("LLM warmup complete.")
        except Exception as exc:
            logger.warning("LLM warmup skipped: %s", exc)
    threading.Thread(target=_warmup, daemon=True).start()
    logger.info("Startup complete. Ready to serve.")
    yield
    logger.info("TurkRAG API shutting down.")
    stop_worker()
    from api.db import _pool
    if _pool is not None:
        _pool.closeall()
        logger.info("DB connection pool closed.")


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
                        password_hash TEXT,
                        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
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

                    CREATE TABLE IF NOT EXISTS document_permissions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL,
                        permission_level TEXT NOT NULL CHECK (permission_level IN ('viewer', 'editor', 'owner')),
                        granted_by TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(document_id, user_id)
                    );

                    CREATE TABLE IF NOT EXISTS eval_runs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        run_label TEXT,
                        config_json JSONB,
                        metrics_json JSONB,
                        per_query_json JSONB,
                        num_queries INT,
                        avg_score NUMERIC(5,4),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    CREATE TABLE IF NOT EXISTS ingestion_jobs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                        document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                        filename TEXT NOT NULL,
                        file_path TEXT,
                        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                        error_message TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        started_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ
                    );

                    CREATE TABLE IF NOT EXISTS document_versions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        version INT NOT NULL DEFAULT 1,
                        filename TEXT NOT NULL,
                        chunk_count INT,
                        is_current BOOLEAN DEFAULT true,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );

                    ALTER TABLE documents ADD COLUMN IF NOT EXISTS version INT DEFAULT 1;
                    ALTER TABLE documents ADD COLUMN IF NOT EXISTS parent_id UUID REFERENCES documents(id);
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
                    ALTER TABLE eval_runs ADD COLUMN IF NOT EXISTS run_label TEXT;
                    ALTER TABLE eval_runs ADD COLUMN IF NOT EXISTS config_json JSONB;
                    ALTER TABLE eval_runs ADD COLUMN IF NOT EXISTS per_query_json JSONB;

                    CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON sessions(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
                    CREATE INDEX IF NOT EXISTS idx_query_logs_tenant ON query_logs(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
                    CREATE INDEX IF NOT EXISTS idx_doc_permissions_user ON document_permissions(user_id);
                    CREATE INDEX IF NOT EXISTS idx_doc_permissions_doc ON document_permissions(document_id);
                    CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status);
                    CREATE INDEX IF NOT EXISTS idx_eval_runs_tenant ON eval_runs(tenant_id);
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tenant_email_lower
                        ON users (tenant_id, lower(email));
                """)
        logger.info("PostgreSQL schema ready.")
    except Exception as exc:
        logger.error("Failed to initialise PostgreSQL schema: %s", exc)
    finally:
        conn.close()


def _rate_limit_key(request: Request) -> str:
    """Key by tenant_id from JWT if present, otherwise fall back to IP.

    This ensures each tenant has its own independent rate bucket.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from api.auth import decode_token
            claims = decode_token(auth[7:])
            return f"tenant:{claims['tenant_id']}"
        except Exception:
            pass
    return get_remote_address(request)


# Per-tenant rate limiter — 60 requests/minute per tenant (or IP as fallback)
RATE_LIMIT = os.getenv("RATE_LIMIT", "60/minute")
limiter = Limiter(key_func=_rate_limit_key, default_limits=[RATE_LIMIT])

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
app.include_router(evaluation.router)
app.include_router(export.router)
app.include_router(permissions.router)
app.include_router(users.router)


# Simple token creation endpoint (dev convenience — replace with proper auth in production)
@app.post("/auth/token", tags=["auth"])
async def get_token(body: DevTokenRequest):
    """Issue a member JWT for dev/testing."""
    if not ENABLE_DEV_AUTH:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Development auth is disabled")
    token = create_token(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        role="member",
        email=body.user_id,
        dev=True,
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", tags=["auth"])
async def login(body: LoginRequest):
    """Authenticate a tenant user with email/password."""
    from api.db import get_conn

    tenant_slug = body.tenant_slug.strip()
    email = body.email.strip().lower()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.tenant_id, u.email, u.password_hash, u.role, u.is_active,
                          t.name, t.slug
                   FROM users u
                   JOIN tenants t ON t.id = u.tenant_id
                   WHERE t.slug=%s AND lower(u.email)=lower(%s)""",
                (tenant_slug, email),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[5] or not row[3] or not verify_password(body.password, row[3]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_token(tenant_id=str(row[1]), user_id=str(row[0]), role=row[4], email=row[2])
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant": {"id": str(row[1]), "name": row[6], "slug": row[7]},
        "user": {"id": str(row[0]), "email": row[2], "role": row[4], "is_active": bool(row[5])},
    }


@app.post("/auth/mock-login", tags=["auth"])
async def mock_login(body: MockAdminLoginRequest):
    """Issue a mock admin JWT after checking the built-in dashboard credentials."""
    from api.db import get_conn

    if not ENABLE_DEV_AUTH:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Development auth is disabled")
    email = body.email.strip()
    password = body.password
    tenant_slug = body.tenant_slug.strip()
    if not validate_mock_admin(email, password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug FROM tenants WHERE slug=%s", (tenant_slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")
    finally:
        conn.close()

    token = create_token(
        tenant_id=str(row[0]),
        user_id=email,
        role="admin",
        email=email,
        dev=True,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant": {"id": str(row[0]), "name": row[1], "slug": row[2]},
        "user": {"email": email, "role": "admin"},
    }


@app.post("/auth/admin/switch-tenant", tags=["auth"])
async def switch_admin_tenant(body: AdminTenantSwitchRequest, payload: dict = Depends(require_admin)):
    """Issue a new admin JWT for another tenant after authenticating the current admin token."""
    from api.db import get_conn

    tenant_slug = body.tenant_slug.strip()
    user_row = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug FROM tenants WHERE slug=%s", (tenant_slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")
            if not payload.get("dev"):
                cur.execute(
                    """SELECT id, email, role, is_active FROM users
                       WHERE tenant_id=%s AND lower(email)=lower(%s)""",
                    (row[0], payload.get("email", "")),
                )
                user_row = cur.fetchone()
                if not user_row or not user_row[3] or user_row[2] != "admin":
                    raise HTTPException(status_code=403, detail="Admin is not active in destination tenant")
    finally:
        conn.close()

    email = str(payload.get("email") or payload.get("user_id", "")).strip() or "admin"
    user_id = str(user_row[0]) if user_row else email
    token = create_token(
        tenant_id=str(row[0]),
        user_id=user_id,
        role="admin",
        email=email,
        dev=bool(payload.get("dev")),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant": {"id": str(row[0]), "name": row[1], "slug": row[2]},
        "user": {"email": email, "role": "admin"},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
