"""Document permission management endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import get_tenant_id
from api.db import get_conn
from api.rbac import grant_access, list_document_permissions, revoke_access

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["permissions"])


class GrantPermissionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    level: str = Field(..., pattern="^(viewer|editor|owner)$")


@router.post("/{doc_id}/permissions", status_code=status.HTTP_201_CREATED)
async def grant_document_access(
    doc_id: str,
    body: GrantPermissionRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    """Grant access to a document for a user."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM documents WHERE id=%s AND tenant_id=%s",
                (doc_id, tenant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")
        grant_access(doc_id, body.user_id, body.level, "api", conn)
    finally:
        conn.close()
    return {"status": "granted", "document_id": doc_id, "user_id": body.user_id, "level": body.level}


@router.delete("/{doc_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_document_access(
    doc_id: str,
    user_id: str,
    tenant_id: str = Depends(get_tenant_id),
):
    """Revoke a user's access to a document."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM documents WHERE id=%s AND tenant_id=%s",
                (doc_id, tenant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")
        if not revoke_access(doc_id, user_id, conn):
            raise HTTPException(status_code=404, detail="Permission not found")
    finally:
        conn.close()


@router.get("/{doc_id}/permissions")
async def get_document_permissions(
    doc_id: str,
    tenant_id: str = Depends(get_tenant_id),
):
    """List all permissions for a document."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM documents WHERE id=%s AND tenant_id=%s",
                (doc_id, tenant_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")
        return list_document_permissions(doc_id, conn)
    finally:
        conn.close()
