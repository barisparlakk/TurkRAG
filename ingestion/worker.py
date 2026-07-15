"""Background ingestion worker that polls for pending jobs."""

import logging
import threading
from contextlib import contextmanager

from api.config import positive_int_env

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

POLL_INTERVAL_SECONDS = positive_int_env("INGESTION_POLL_INTERVAL_SECONDS", 5)
HEARTBEAT_INTERVAL_SECONDS = positive_int_env("INGESTION_HEARTBEAT_INTERVAL_SECONDS", 30)


def _mark_document_error(document_id: str | None):
    """Best-effort document status update for terminal ingestion failures."""
    if not document_id:
        return
    from api.db import get_conn

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE documents SET status='error' WHERE id=%s", (document_id,))
    except Exception as exc:
        logger.warning("Could not mark document %s as error: %s", document_id, exc)
    finally:
        conn.close()


class _JobHeartbeat:
    """Refresh a job heartbeat while long-running ingestion work is active."""

    def __init__(self, job_id: str, interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS):
        self.job_id = job_id
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._send()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"ingestion-heartbeat-{self.job_id}")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop_event.wait(timeout=self.interval_seconds):
            self._send()

    def _send(self):
        from api.db import get_conn
        from ingestion.queue import heartbeat_job

        conn = None
        try:
            conn = get_conn()
            heartbeat_job(self.job_id, conn)
        except Exception as exc:
            logger.warning("Could not refresh heartbeat for job %s: %s", self.job_id, exc)
        finally:
            if conn is not None:
                conn.close()


@contextmanager
def _active_job_heartbeat(job_id: str):
    heartbeat = _JobHeartbeat(job_id)
    heartbeat.start()
    try:
        yield
    finally:
        heartbeat.stop()


def _process_job(job: dict):
    """Run full ingestion pipeline for a single job."""
    from api.db import get_conn
    from ingestion.chunker import TurkishChunker
    from ingestion.indexer import TenantIndexer
    from ingestion.parser import parse_document
    from ingestion.queue import complete_job, fail_job

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT t.slug, d.status
                   FROM tenants t
                   LEFT JOIN documents d ON d.id=%s AND d.tenant_id=t.id
                   WHERE t.id=%s""",
                (job["document_id"], job["tenant_id"]),
            )
            row = cur.fetchone()
            if not row:
                result = fail_job(job["id"], f"Tenant {job['tenant_id']} not found", conn, retry=False)
                if result and result["status"] == "failed":
                    _mark_document_error(job.get("document_id"))
                return
            tenant_slug = row[0]
            document_status = row[1]
            if document_status == "ready":
                complete_job(job["id"], conn)
                logger.info("Job %s completed because document %s is already ready", job["id"], job["document_id"])
                return
    finally:
        conn.close()

    try:
        with _active_job_heartbeat(job["id"]):
            text = parse_document(job["file_path"])
            chunks = TurkishChunker().chunk(text)
            logger.info("Job %s: %d chars → %d chunks", job["id"], len(text), len(chunks))

            TenantIndexer().ingest(job["document_id"], tenant_slug, job["filename"], chunks)

        conn = get_conn()
        try:
            complete_job(job["id"], conn)
        finally:
            conn.close()
        logger.info("Job %s completed", job["id"])

    except Exception as exc:
        logger.exception("Job %s failed: %s", job["id"], exc)
        conn = get_conn()
        try:
            result = fail_job(job["id"], str(exc), conn)
        finally:
            conn.close()
        if result and result["status"] == "failed":
            _mark_document_error(job.get("document_id"))


def _worker_loop():
    """Main worker loop: poll for jobs every configured interval."""
    from api.db import get_conn
    from ingestion.queue import pick_next_job, recover_stale_jobs

    logger.info("Ingestion worker started (poll every %ds)", POLL_INTERVAL_SECONDS)

    while not _stop_event.is_set():
        try:
            conn = get_conn()
            try:
                recovered = recover_stale_jobs(conn)
                for stale_job in recovered:
                    logger.warning(
                        "Recovered stale job %s as %s (attempt %d/%d)",
                        stale_job["id"],
                        stale_job["status"],
                        stale_job["attempts"],
                        stale_job["max_attempts"],
                    )
                    if stale_job["status"] == "failed":
                        _mark_document_error(stale_job.get("document_id"))
                job = pick_next_job(conn)
            finally:
                conn.close()

            if job:
                logger.info("Processing job %s: %s", job["id"], job["filename"])
                _process_job(job)
            else:
                _stop_event.wait(timeout=POLL_INTERVAL_SECONDS)
        except Exception as exc:
            logger.error("Worker loop error: %s", exc)
            _stop_event.wait(timeout=POLL_INTERVAL_SECONDS)


def start_worker():
    """Start the background worker thread (idempotent)."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="ingestion-worker")
    _worker_thread.start()


def stop_worker():
    """Signal the worker to stop."""
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=10)
