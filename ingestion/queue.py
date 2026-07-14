"""PostgreSQL-based async ingestion job queue."""

import logging

from api.config import positive_int_env

logger = logging.getLogger(__name__)

MAX_JOB_ATTEMPTS = positive_int_env("INGESTION_MAX_JOB_ATTEMPTS", 3)
RETRY_DELAY_SECONDS = positive_int_env("INGESTION_RETRY_DELAY_SECONDS", 60)
STALE_JOB_TIMEOUT_SECONDS = positive_int_env("INGESTION_STALE_JOB_TIMEOUT_SECONDS", 900)
ERROR_MESSAGE_MAX_LENGTH = 500


def _truncate_error(error_message: str) -> str:
    return str(error_message)[:ERROR_MESSAGE_MAX_LENGTH]


def enqueue_job(tenant_id: str, document_id: str, filename: str, file_path: str, conn) -> str:
    """Add a new ingestion job. Returns job UUID."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ingestion_jobs
                   (tenant_id, document_id, filename, file_path, status, max_attempts)
               VALUES (%s, %s, %s, %s, 'pending', %s)
               RETURNING id""",
            (tenant_id, document_id, filename, file_path, MAX_JOB_ATTEMPTS),
        )
        return str(cur.fetchone()[0])


def pick_next_job(conn) -> dict | None:
    """Atomically pick the next runnable job (SKIP LOCKED). Returns job dict or None."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE ingestion_jobs
               SET status='processing',
                   attempts=attempts + 1,
                   started_at=NOW(),
                   last_heartbeat_at=NOW(),
                   completed_at=NULL
               WHERE id = (
                   SELECT id FROM ingestion_jobs
                   WHERE status='pending'
                     AND attempts < max_attempts
                     AND (retry_after IS NULL OR retry_after <= NOW())
                   ORDER BY created_at ASC
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED
               )
               RETURNING id, tenant_id, document_id, filename, file_path,
                         attempts, max_attempts, last_heartbeat_at"""
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
            "attempts": int(row[5]),
            "max_attempts": int(row[6]),
            "last_heartbeat_at": str(row[7]) if row[7] else None,
        }


def heartbeat_job(job_id: str, conn):
    """Refresh the processing heartbeat for a running job."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE ingestion_jobs
               SET last_heartbeat_at=NOW()
               WHERE id=%s AND status='processing'""",
            (job_id,),
        )


def complete_job(job_id: str, conn):
    """Mark job as completed."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE ingestion_jobs
               SET status='completed',
                   completed_at=NOW(),
                   retry_after=NULL,
                   last_heartbeat_at=NOW()
               WHERE id=%s""",
            (job_id,),
        )


def fail_job(job_id: str, error_message: str, conn, retry: bool = True) -> dict | None:
    """Record a failure and retry while attempts remain; otherwise mark failed."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE ingestion_jobs
               SET status = CASE
                       WHEN %s AND attempts < max_attempts THEN 'pending'
                       ELSE 'failed'
                   END,
                   error_message=%s,
                   retry_after = CASE
                       WHEN %s AND attempts < max_attempts THEN NOW() + (%s * INTERVAL '1 second')
                       ELSE NULL
                   END,
                   completed_at = CASE
                       WHEN %s AND attempts < max_attempts THEN NULL
                       ELSE NOW()
                   END,
                   last_heartbeat_at=NULL
               WHERE id=%s
               RETURNING status, attempts, max_attempts, retry_after, completed_at""",
            (
                retry,
                _truncate_error(error_message),
                retry,
                RETRY_DELAY_SECONDS,
                retry,
                job_id,
            ),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "status": row[0],
            "attempts": int(row[1]),
            "max_attempts": int(row[2]),
            "retry_after": str(row[3]) if row[3] else None,
            "completed_at": str(row[4]) if row[4] else None,
        }


def recover_stale_jobs(conn) -> list[dict]:
    """Requeue or fail processing jobs whose worker heartbeat has expired."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """WITH stale AS (
                   SELECT id FROM ingestion_jobs
                   WHERE status='processing'
                     AND COALESCE(last_heartbeat_at, started_at, created_at)
                         < NOW() - (%s * INTERVAL '1 second')
                   FOR UPDATE SKIP LOCKED
               )
               UPDATE ingestion_jobs j
               SET status = CASE
                       WHEN j.attempts >= j.max_attempts THEN 'failed'
                       ELSE 'pending'
                   END,
                   error_message = CASE
                       WHEN j.attempts >= j.max_attempts
                           THEN 'Job timed out while processing'
                       ELSE j.error_message
                   END,
                   retry_after = CASE
                       WHEN j.attempts >= j.max_attempts THEN NULL
                       ELSE NOW()
                   END,
                   started_at=NULL,
                   last_heartbeat_at=NULL,
                   completed_at = CASE
                       WHEN j.attempts >= j.max_attempts THEN NOW()
                       ELSE NULL
                   END
               FROM stale
               WHERE j.id = stale.id
               RETURNING j.id, j.document_id, j.status, j.attempts, j.max_attempts""",
            (STALE_JOB_TIMEOUT_SECONDS,),
        )
        return [
            {
                "id": str(row[0]),
                "document_id": str(row[1]) if row[1] else None,
                "status": row[2],
                "attempts": int(row[3]),
                "max_attempts": int(row[4]),
            }
            for row in cur.fetchall()
        ]


def get_job_status(job_id: str, conn) -> dict | None:
    """Get current status of a job."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, tenant_id, document_id, filename, status, error_message,
                      created_at, started_at, completed_at, attempts, max_attempts,
                      last_heartbeat_at, retry_after
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
            "attempts": int(row[9]),
            "max_attempts": int(row[10]),
            "last_heartbeat_at": str(row[11]) if row[11] else None,
            "retry_after": str(row[12]) if row[12] else None,
        }
