"""Document upload, list, and delete endpoints."""

import hashlib
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from api.auth import get_tenant_id
from api.db import get_conn
from api.schemas import DocumentListItem, DocumentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx", ".xls", ".csv"}


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_tenant_id),
):
    """Upload a document for ingestion. Returns immediately; processing is async."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    # Reject duplicate uploads for this tenant; insert processing row atomically
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM documents WHERE tenant_id=%s AND file_hash=%s AND status='ready'",
                (tenant_id, file_hash),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="This document has already been uploaded for this tenant")

            document_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO documents (id, tenant_id, filename, file_hash, status) VALUES (%s, %s, %s, %s, 'processing')",
                (document_id, tenant_id, file.filename, file_hash),
            )
    finally:
        conn.close()

    # Save file to disk
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / f"{document_id}{suffix}"
    save_path.write_bytes(content)
    logger.info("Saved upload: %s → %s (%d bytes)", file.filename, save_path, len(content))

    # Invalidate semantic cache for this tenant
    try:
        from retrieval.semantic_cache import get_cache
        get_cache().invalidate(tenant_id)
    except Exception as exc:
        logger.warning("Cache invalidation failed: %s", exc)

    # Trigger background ingestion
    background_tasks.add_task(_ingest_document, document_id, str(save_path), file.filename, tenant_id)

    return DocumentUploadResponse(document_id=document_id, filename=file.filename, status="processing")


@router.get("", response_model=list[DocumentListItem])
async def list_documents(tenant_id: str = Depends(get_tenant_id)):
    """List all documents for the current tenant."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, chunk_count, status, created_at FROM documents WHERE tenant_id=%s ORDER BY created_at DESC",
                (tenant_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        DocumentListItem(
            id=str(r[0]),
            filename=r[1],
            chunk_count=r[2],
            status=r[3],
            created_at=str(r[4]),
        )
        for r in rows
    ]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, tenant_id: str = Depends(get_tenant_id)):
    """Remove a document from Qdrant, BM25, and PostgreSQL."""
    tenant_slug = None
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """SELECT d.id, d.tenant_id, t.slug
                   FROM documents d JOIN tenants t ON t.id = d.tenant_id
                   WHERE d.id=%s""",
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Document not found")
            if str(row[1]) != tenant_id:
                raise HTTPException(status_code=403, detail="Access denied")
            tenant_slug = row[2]
            cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))
    finally:
        conn.close()

    if tenant_slug:
        from ingestion.indexer import delete_document_vectors
        try:
            delete_document_vectors(doc_id, tenant_slug)
        except Exception as exc:
            logger.warning("Could not delete Qdrant vectors for doc %s: %s", doc_id, exc)

    logger.info("Deleted document %s from tenant %s", doc_id, tenant_id)


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, tenant_id: str = Depends(get_tenant_id)):
    """Get ingestion job status."""
    from ingestion.queue import get_job_status as _get_job_status
    conn = get_conn()
    try:
        result = _get_job_status(job_id, conn)
    finally:
        conn.close()
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    if result["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return result


def _ingest_document(document_id: str, file_path: str, filename: str, tenant_id: str):
    """Background task: parse → chunk → embed → index."""
    logger.info("Background ingestion started: doc=%s file=%s", document_id, file_path)

    row = None
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
            row = cur.fetchone()
    except Exception as exc:
        logger.error("DB error resolving tenant for doc %s: %s", document_id, exc)
    finally:
        if conn is not None:
            conn.close()

    if not row:
        logger.error("Tenant %s not found — aborting ingestion for doc %s", tenant_id, document_id)
        return

    tenant_slug = row[0]

    try:
        from ingestion.chunker import TurkishChunker
        from ingestion.indexer import TenantIndexer
        from ingestion.parser import parse_document

        text = parse_document(file_path)
        chunks = TurkishChunker().chunk(text)
        logger.info("Doc %s: %d chars → %d chunks", document_id, len(text), len(chunks))

        TenantIndexer().ingest(document_id, tenant_slug, filename, chunks)
        logger.info("Ingestion complete: doc=%s", document_id)
    except Exception as exc:
        logger.exception("Ingestion failed for doc %s: %s", document_id, exc)
        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("UPDATE documents SET status='error' WHERE id=%s", (document_id,))
        finally:
            conn.close()
