"""Background ingestion worker that polls for pending jobs."""

import logging
import threading

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

POLL_INTERVAL = 5


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
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (job["tenant_id"],))
            row = cur.fetchone()
            if not row:
                fail_job(job["id"], f"Tenant {job['tenant_id']} not found", conn)
                return
            tenant_slug = row[0]
    finally:
        conn.close()

    try:
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
            fail_job(job["id"], str(exc)[:500], conn)
        finally:
            conn.close()


def _worker_loop():
    """Main worker loop: poll for jobs every POLL_INTERVAL seconds."""
    from api.db import get_conn
    from ingestion.queue import pick_next_job

    logger.info("Ingestion worker started (poll every %ds)", POLL_INTERVAL)

    while not _stop_event.is_set():
        try:
            conn = get_conn()
            try:
                job = pick_next_job(conn)
            finally:
                conn.close()

            if job:
                logger.info("Processing job %s: %s", job["id"], job["filename"])
                _process_job(job)
            else:
                _stop_event.wait(timeout=POLL_INTERVAL)
        except Exception as exc:
            logger.error("Worker loop error: %s", exc)
            _stop_event.wait(timeout=POLL_INTERVAL)


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
