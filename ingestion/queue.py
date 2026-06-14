"""PostgreSQL-based async ingestion job queue."""

import logging

logger = logging.getLogger(__name__)


def enqueue_job(tenant_id: str, document_id: str, filename: str, file_path: str, conn) -> str:
    """Add a new ingestion job. Returns job UUID."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ingestion_jobs (tenant_id, document_id, filename, file_path, status)
               VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
            (tenant_id, document_id, filename, file_path),
        )
        return str(cur.fetchone()[0])


def pick_next_job(conn) -> dict | None:
    """Atomically pick the next pending job (SKIP LOCKED). Returns job dict or None."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE ingestion_jobs
               SET status='processing', started_at=NOW()
               WHERE id = (
                   SELECT id FROM ingestion_jobs
                   WHERE status='pending'
                   ORDER BY created_at ASC
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED
               )
               RETURNING id, tenant_id, document_id, filename, file_path"""
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "document_id": str(row[2]),
            "filename": row[3],
            "file_path": row[4],
        }


def complete_job(job_id: str, conn):
    """Mark job as completed."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion_jobs SET status='completed', completed_at=NOW() WHERE id=%s",
            (job_id,),
        )


def fail_job(job_id: str, error_message: str, conn):
    """Mark job as failed with error message."""
    with conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion_jobs SET status='failed', error_message=%s, completed_at=NOW() WHERE id=%s",
            (error_message, job_id),
        )


def get_job_status(job_id: str, conn) -> dict | None:
    """Get current status of a job."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, tenant_id, document_id, filename, status, error_message,
                      created_at, started_at, completed_at
               FROM ingestion_jobs WHERE id=%s""",
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "tenant_id": str(row[1]),
            "document_id": str(row[2]),
            "filename": row[3],
            "status": row[4],
            "error_message": row[5],
            "created_at": str(row[6]) if row[6] else None,
            "started_at": str(row[7]) if row[7] else None,
            "completed_at": str(row[8]) if row[8] else None,
        }
