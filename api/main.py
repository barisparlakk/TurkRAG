"""TurkRAG FastAPI application entrypoint."""

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
REQUIRED_ALEMBIC_REVISION = "0003_backfill_document_permissions"
AUTO_INIT_SCHEMA = os.getenv("AUTO_INIT_SCHEMA", "false").lower() == "true"
REQUIRED_TABLES = {
    "tenants",
    "documents",
    "users",
    "sessions",
    "messages",
    "query_logs",
    "document_permissions",
    "eval_runs",
    "ingestion_jobs",
    "document_versions",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks and yield to serve requests."""
    logger.info("TurkRAG API starting up…")
    jwt_secret = os.getenv("JWT_SECRET", "change_this_in_production")
    if APP_ENV == "production" and jwt_secret == "change_this_in_production":
        raise RuntimeError("JWT_SECRET must be set before running in production")
    if APP_ENV == "production" and ENABLE_DEV_AUTH:
        raise RuntimeError("ENABLE_DEV_AUTH must be false before running in production")
    if APP_ENV == "production" and AUTO_INIT_SCHEMA:
        raise RuntimeError("AUTO_INIT_SCHEMA must be false before running in production")
    if jwt_secret == "change_this_in_production":
        logger.warning(
            "JWT_SECRET is the default insecure value. "
            "Set JWT_SECRET env var before deploying to production."
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_schema_ready()
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


def _run_alembic_upgrade():
    """Run Alembic upgrade for explicit local development bootstrap."""
    from alembic import command
    from alembic.config import Config

    logger.info("AUTO_INIT_SCHEMA enabled — running Alembic upgrade head.")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


def _ensure_schema_ready():
    """Fail startup unless the database is at the required Alembic baseline."""
    import psycopg2

    if AUTO_INIT_SCHEMA:
        if APP_ENV == "production":
            raise RuntimeError("AUTO_INIT_SCHEMA must be false before running in production")
        _run_alembic_upgrade()

    try:
        conn = psycopg2.connect(POSTGRES_URL)
    except Exception as exc:
        raise RuntimeError("Failed to connect to PostgreSQL. Check POSTGRES_URL.") from exc

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.alembic_version')")
            version_table = cur.fetchone()
            if not version_table or version_table[0] is None:
                raise RuntimeError("Database schema is not migrated. Run: alembic upgrade head")

            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            current_revision = row[0] if row else None
            if current_revision != REQUIRED_ALEMBIC_REVISION:
                raise RuntimeError(
                    f"Database migration revision mismatch: expected "
                    f"{REQUIRED_ALEMBIC_REVISION}, got {current_revision or 'none'}"
                )

            cur.execute(
                """SELECT table_name
                   FROM information_schema.tables
                   WHERE table_schema='public' AND table_name = ANY(%s)""",
                (list(REQUIRED_TABLES),),
            )
            existing_tables = {row[0] for row in cur.fetchall()}
            missing = sorted(REQUIRED_TABLES - existing_tables)
            if missing:
                raise RuntimeError(f"Database schema is incomplete. Missing tables: {', '.join(missing)}")

        logger.info("Database schema verified at revision %s.", REQUIRED_ALEMBIC_REVISION)
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
