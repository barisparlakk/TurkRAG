"""Document upload, list, and delete endpoints."""

import hashlib
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.auth import get_current_user, get_tenant_id
from api.db import get_conn
from api.rbac import (
    get_accessible_document_ids,
    grant_access,
    user_has_document_management_access,
)
from api.schemas import DocumentListItem, DocumentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads"))
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx", ".xls", ".csv"}
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a document for ingestion. Returns immediately; processing is async."""
    tenant_id = user["tenant_id"]
    safe_filename = Path(file.filename or "upload").name
    suffix = Path(safe_filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex}{suffix}.tmp"
    total_bytes = 0
    hasher = hashlib.sha256()

    try:
        with temp_path.open("wb") as out:
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"File too large. Maximum allowed size is {MAX_UPLOAD_BYTES} bytes.",
                    )
                hasher.update(chunk)
                out.write(chunk)
    except HTTPException:
        temp_path.unlink(missing_ok=True)
        raise
    except Exception:
        temp_path.unlink(missing_ok=True)
        logger.exception("Failed to stream upload: %s", safe_filename)
        raise

    file_hash = hasher.hexdigest()
    document_id = None
    document_inserted = False
    save_path = None

    try:
        # Reject duplicate uploads for this tenant; insert processing row atomically
        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM documents WHERE tenant_id=%s AND file_hash=%s AND status='ready'",
                    (tenant_id, file_hash),
                )
                if cur.fetchone():
                    raise HTTPException(
                        status_code=409,
                        detail="This document has already been uploaded for this tenant",
                    )

                document_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO documents (id, tenant_id, filename, file_hash, status) VALUES (%s, %s, %s, %s, 'processing')",
                    (document_id, tenant_id, safe_filename, file_hash),
                )
                document_inserted = True
            grant_access(document_id, user["id"], "owner", user["id"], conn)
        finally:
            conn.close()

        save_path = UPLOAD_DIR / f"{document_id}{suffix}"
        temp_path.replace(save_path)
        logger.info("Saved upload: %s → %s (%d bytes)", safe_filename, save_path, total_bytes)

        # Invalidate semantic cache for this tenant
        try:
            from retrieval.semantic_cache import get_cache
            get_cache().invalidate(tenant_id)
        except Exception as exc:
            logger.warning("Cache invalidation failed: %s", exc)

        from ingestion.queue import enqueue_job

        conn = get_conn()
        try:
            job_id = enqueue_job(tenant_id, document_id, safe_filename, str(save_path), conn)
        finally:
            conn.close()
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        if save_path is not None:
            save_path.unlink(missing_ok=True)
        if document_inserted and document_id is not None:
            _delete_document_row(document_id)
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Document upload failed") from exc

    return DocumentUploadResponse(document_id=document_id, job_id=job_id, filename=safe_filename, status="processing")


def _delete_document_row(document_id: str) -> None:
    """Best-effort cleanup for uploads that fail before returning success."""
    conn = None
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id=%s", (document_id,))
    except Exception as exc:
        logger.warning("Upload rollback could not delete document row %s: %s", document_id, exc)
    finally:
        if conn is not None:
            conn.close()


@router.get("", response_model=list[DocumentListItem])
async def list_documents(user: dict = Depends(get_current_user)):
    """List all documents for the current tenant."""
    tenant_id = user["tenant_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user.get("role") == "admin":
                cur.execute(
                    """SELECT id, filename, chunk_count, status, created_at
                       FROM documents
                       WHERE tenant_id=%s
                       ORDER BY created_at DESC""",
                    (tenant_id,),
                )
            else:
                accessible_ids = get_accessible_document_ids(user["id"], tenant_id, conn)
                if not accessible_ids:
                    return []
                cur.execute(
                    """SELECT id, filename, chunk_count, status, created_at
                       FROM documents
                       WHERE tenant_id=%s AND id = ANY(%s)
                       ORDER BY created_at DESC""",
                    (tenant_id, accessible_ids),
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
async def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    """Remove a document from Qdrant, BM25, and PostgreSQL."""
    tenant_id = user["tenant_id"]
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
            if not user_has_document_management_access(user, doc_id, conn, required_level="editor"):
                raise HTTPException(status_code=403, detail="Document editor or admin access required")
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


@router.get("/jobs")
async def list_jobs(limit: int = 30, tenant_id: str = Depends(get_tenant_id)):
    """List recent ingestion jobs for the current tenant."""
    limit = min(max(limit, 1), 100)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, tenant_id, document_id, filename, status, error_message,
                          created_at, started_at, completed_at, attempts, max_attempts,
                          last_heartbeat_at, retry_after
                   FROM ingestion_jobs
                   WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": str(r[0]),
            "tenant_id": str(r[1]),
            "document_id": str(r[2]) if r[2] else None,
            "filename": r[3],
            "status": r[4],
            "error_message": r[5],
            "created_at": str(r[6]) if r[6] else None,
            "started_at": str(r[7]) if r[7] else None,
            "completed_at": str(r[8]) if r[8] else None,
            "attempts": int(r[9]),
            "max_attempts": int(r[10]),
            "last_heartbeat_at": str(r[11]) if r[11] else None,
            "retry_after": str(r[12]) if r[12] else None,
        }
        for r in rows
    ]


def _ingest_document(document_id: str, file_path: str, filename: str, tenant_id: str, job_id: str | None = None):
    """Background task: parse → chunk → embed → index."""
    logger.info("Background ingestion started: doc=%s file=%s", document_id, file_path)

    row = None
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
            row = cur.fetchone()
        if job_id:
            # Mark this specific background task as processing without competing for queue workers.
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE ingestion_jobs SET status='processing', started_at=NOW() WHERE id=%s",
                    (job_id,),
                )
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
        if job_id:
            conn = get_conn()
            try:
                from ingestion.queue import complete_job
                complete_job(job_id, conn)
            finally:
                conn.close()
        logger.info("Ingestion complete: doc=%s", document_id)
    except Exception as exc:
        logger.exception("Ingestion failed for doc %s: %s", document_id, exc)
        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("UPDATE documents SET status='error' WHERE id=%s", (document_id,))
            if job_id:
                from ingestion.queue import fail_job
                fail_job(job_id, str(exc), conn)
        finally:
            conn.close()
