"""Tenant CRUD — admin only."""

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import require_admin
from api.db import get_conn
from api.schemas import TenantCreate, TenantResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


@router.get("/by-slug/{slug}", response_model=TenantResponse)
async def get_tenant_by_slug(slug: str):
    """Public endpoint — resolve a tenant slug to its UUID (needed for login)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, created_at FROM tenants WHERE slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
    finally:
        conn.close()
    return TenantResponse(id=str(row[0]), name=row[1], slug=row[2], created_at=str(row[3]))


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(body: TenantCreate, _=Depends(require_admin)):
    """Provision a new tenant: create DB row + Qdrant collection."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            # Check for duplicate slug
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (body.slug,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"Tenant slug '{body.slug}' already exists")

            tenant_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO tenants (id, name, slug) VALUES (%s, %s, %s) RETURNING id, name, slug, created_at",
                (tenant_id, body.name, body.slug),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    # Provision Qdrant collection
    _provision_qdrant(body.slug)

    logger.info("Created tenant: name=%s slug=%s id=%s", body.name, body.slug, tenant_id)
    return TenantResponse(id=row[0], name=row[1], slug=row[2], created_at=str(row[3]))


@router.get("", response_model=list[TenantResponse])
async def list_tenants(_=Depends(require_admin)):
    """List all tenants."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, created_at FROM tenants ORDER BY created_at DESC")
            rows = cur.fetchall()
    finally:
        conn.close()

    return [TenantResponse(id=str(r[0]), name=r[1], slug=r[2], created_at=str(r[3])) for r in rows]


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(slug: str, _=Depends(require_admin)):
    """Delete a tenant and all their data (Qdrant + PostgreSQL)."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug=%s", (slug,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found")
            cur.execute("DELETE FROM tenants WHERE slug=%s", (slug,))
    finally:
        conn.close()

    # Remove Qdrant collection
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=QDRANT_URL)
        client.delete_collection(f"tenant_{slug}")
        logger.info("Deleted Qdrant collection for tenant '%s'", slug)
    except Exception as exc:
        logger.warning("Could not delete Qdrant collection for '%s': %s", slug, exc)

    # Remove BM25 index file
    from pathlib import Path
    bm25_path = Path(os.getenv("BM25_INDEX_DIR", "indexes")) / f"bm25_{slug}.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
        logger.info("Deleted BM25 index for tenant '%s'", slug)

    logger.info("Tenant '%s' fully deleted", slug)


def _provision_qdrant(tenant_slug: str):
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    client = QdrantClient(url=QDRANT_URL)
    collection_name = f"tenant_{tenant_slug}"
    existing = [c.name for c in client.get_collections().collections]
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )
        logger.info("Qdrant collection created: %s", collection_name)
