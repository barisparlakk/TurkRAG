"""JWT authentication and tenant extraction for the TurkRAG API."""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "change_this_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=True)


def create_token(tenant_id: str, user_id: str, role: str) -> str:
    """Encode a signed JWT with tenant/user claims."""
    from jose import jwt

    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    from jose import jwt, JWTError

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: decode JWT and return full payload."""
    return decode_token(token)


async def get_tenant_id(payload: dict = Depends(get_current_payload)) -> str:
    """FastAPI dependency: extract tenant_id from JWT payload."""
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing tenant_id in token")
    return tenant_id


async def require_admin(payload: dict = Depends(get_current_payload)) -> dict:
    """FastAPI dependency: require 'admin' role."""
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return payload
