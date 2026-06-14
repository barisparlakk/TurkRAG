"""Tenant-scoped user management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, hash_password, require_admin, verify_password
from api.db import get_conn
from api.schemas import PasswordChangeRequest, UserCreateRequest, UserResponse, UserUpdateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


def _row_to_user(row) -> UserResponse:
    return UserResponse(
        id=str(row[0]),
        tenant_id=str(row[1]),
        email=row[2],
        role=row[3],
        is_active=bool(row[4]),
        created_at=str(row[5]),
    )


@router.get("", response_model=list[UserResponse])
async def list_users(admin: dict = Depends(require_admin)):
    """List users in the current tenant."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, tenant_id, email, role, is_active, created_at
                   FROM users WHERE tenant_id=%s ORDER BY created_at DESC""",
                (admin["tenant_id"],),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [_row_to_user(row) for row in rows]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreateRequest, admin: dict = Depends(require_admin)):
    """Create a tenant user with an initial password."""
    email = body.email.strip().lower()
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (tenant_id, email, password_hash, role, is_active)
                   VALUES (%s, %s, %s, %s, true)
                   RETURNING id, tenant_id, email, role, is_active, created_at""",
                (admin["tenant_id"], email, hash_password(body.password), body.role),
            )
            row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=409, detail="User already exists or could not be created") from exc
    finally:
        conn.close()

    logger.info("Admin %s created user %s in tenant %s", admin["email"], email, admin["tenant_id"])
    return _row_to_user(row)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, body: UserUpdateRequest, admin: dict = Depends(require_admin)):
    """Update role and/or active status for a tenant user."""
    if body.role is None and body.is_active is None:
        raise HTTPException(status_code=422, detail="role or is_active is required")

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM users WHERE id=%s AND tenant_id=%s""",
                (user_id, admin["tenant_id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            if body.role is not None:
                cur.execute(
                    "UPDATE users SET role=%s, updated_at=NOW() WHERE id=%s AND tenant_id=%s",
                    (body.role, user_id, admin["tenant_id"]),
                )
            if body.is_active is not None:
                cur.execute(
                    "UPDATE users SET is_active=%s, updated_at=NOW() WHERE id=%s AND tenant_id=%s",
                    (body.is_active, user_id, admin["tenant_id"]),
                )
            cur.execute(
                """SELECT id, tenant_id, email, role, is_active, created_at
                   FROM users WHERE id=%s AND tenant_id=%s""",
                (user_id, admin["tenant_id"]),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    return _row_to_user(row)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(user_id: str, admin: dict = Depends(require_admin)):
    """Deactivate a tenant user instead of hard-deleting them."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE users SET is_active=false, updated_at=NOW()
                   WHERE id=%s AND tenant_id=%s""",
                (user_id, admin["tenant_id"]),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")
    finally:
        conn.close()


@router.post("/me/change-password")
async def change_password(body: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    """Allow an active user to change their own password."""
    if user.get("dev"):
        raise HTTPException(status_code=403, detail="Development users cannot change passwords")

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE id=%s", (user["id"],))
            row = cur.fetchone()
            if not row or not verify_password(body.current_password, row[0]):
                raise HTTPException(status_code=401, detail="Current password is invalid")
            cur.execute(
                "UPDATE users SET password_hash=%s, updated_at=NOW() WHERE id=%s",
                (hash_password(body.new_password), user["id"]),
            )
    finally:
        conn.close()
    return {"status": "ok"}
