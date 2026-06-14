"""JWT authentication and tenant extraction for the TurkRAG API."""

import logging
import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "change_this_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=True)
MOCK_ADMIN_EMAIL = os.getenv("MOCK_ADMIN_EMAIL", "baris@dev.com")
MOCK_ADMIN_PASSWORD = os.getenv("MOCK_ADMIN_PASSWORD", "1234")
APP_ENV = os.getenv("APP_ENV", "development").lower()
ENABLE_DEV_AUTH = os.getenv("ENABLE_DEV_AUTH", "true" if APP_ENV != "production" else "false").lower() == "true"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return pwd_context.verify(password, password_hash)


def create_token(tenant_id: str, user_id: str, role: str, email: str | None = None, dev: bool = False) -> str:
    """Encode a signed JWT with tenant/user claims."""
    from jose import jwt

    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    if email:
        payload["email"] = email
    if dev:
        payload["dev"] = True
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    from jose import JWTError, jwt

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: decode JWT and return full payload."""
    return decode_token(token)


async def get_current_user(payload: dict = Depends(get_current_payload)) -> dict:
    """Return the active DB-backed user for a JWT payload.

    Development tokens are accepted only when ENABLE_DEV_AUTH is true.
    """
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    if not tenant_id or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user claims")

    if payload.get("dev"):
        if not ENABLE_DEV_AUTH:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Development auth is disabled")
        return {
            "id": user_id,
            "tenant_id": tenant_id,
            "email": payload.get("email") or user_id,
            "role": payload.get("role", "member"),
            "is_active": True,
            "dev": True,
        }

    from api.db import get_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, tenant_id, email, role, is_active
                   FROM users WHERE id=%s AND tenant_id=%s""",
                (user_id, tenant_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[4]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")

    return {
        "id": str(row[0]),
        "tenant_id": str(row[1]),
        "email": row[2],
        "role": row[3],
        "is_active": bool(row[4]),
    }


async def get_tenant_id(user: dict = Depends(get_current_user)) -> str:
    """FastAPI dependency: extract tenant_id from JWT payload."""
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant_id in token")
    return tenant_id


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: require 'admin' role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def validate_mock_admin(email: str, password: str) -> bool:
    """Validate the built-in mock admin credentials used by the dashboard."""
    return email.strip().lower() == MOCK_ADMIN_EMAIL.lower() and password == MOCK_ADMIN_PASSWORD
