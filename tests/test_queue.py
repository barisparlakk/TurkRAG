"""Regression tests for ingestion queue durability and recovery."""

import importlib
from unittest.mock import MagicMock, patch

import pytest


class _Cursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_pick_next_job_claims_runnable_job_and_increments_attempts():
    from ingestion.queue import pick_next_job

    cursor = _Cursor(
        fetchone_result=(
            "job-1",
            "tenant-1",
            "doc-1",
            "file.txt",
            "/tmp/file.txt",
            2,
            3,
            "2026-06-16 10:00:00+00",
        )
    )

    job = pick_next_job(_Conn(cursor))

    assert job == {
        "id": "job-1",
        "tenant_id": "tenant-1",
        "document_id": "doc-1",
        "filename": "file.txt",
        "file_path": "/tmp/file.txt",
        "attempts": 2,
        "max_attempts": 3,
        "last_heartbeat_at": "2026-06-16 10:00:00+00",
    }
    query, _ = cursor.queries[0]
    assert "attempts=attempts + 1" in query
    assert "status='pending'" in query
    assert "attempts < max_attempts" in query
    assert "retry_after IS NULL OR retry_after <= NOW()" in query
    assert "FOR UPDATE SKIP LOCKED" in query


def test_fail_job_retries_until_attempts_are_exhausted_and_truncates_error():
    from ingestion.queue import ERROR_MESSAGE_MAX_LENGTH, fail_job

    cursor = _Cursor(fetchone_result=("pending", 1, 3, "2026-06-16 10:01:00+00", None))
    result = fail_job("job-1", "x" * (ERROR_MESSAGE_MAX_LENGTH + 25), _Conn(cursor))

    assert result["status"] == "pending"
    query, params = cursor.queries[0]
    assert "WHEN %s AND attempts < max_attempts THEN 'pending'" in query
    assert "ELSE 'failed'" in query
    assert len(params[1]) == ERROR_MESSAGE_MAX_LENGTH


def test_recover_stale_jobs_requeues_or_fails_processing_jobs():
    from ingestion.queue import recover_stale_jobs

    cursor = _Cursor(
        fetchall_result=[
            ("job-retry", "doc-retry", "pending", 1, 3),
            ("job-failed", "doc-failed", "failed", 3, 3),
        ]
    )

    recovered = recover_stale_jobs(_Conn(cursor))

    assert recovered == [
        {"id": "job-retry", "document_id": "doc-retry", "status": "pending", "attempts": 1, "max_attempts": 3},
        {"id": "job-failed", "document_id": "doc-failed", "status": "failed", "attempts": 3, "max_attempts": 3},
    ]
    query, params = cursor.queries[0]
    assert "status='processing'" in query
    assert "COALESCE(last_heartbeat_at, started_at, created_at)" in query
    assert "WHEN j.attempts >= j.max_attempts THEN 'failed'" in query
    assert params[0] > 0


def test_process_job_completes_successful_job_once():
    from ingestion.worker import _process_job

    tenant_cursor = _Cursor(fetchone_result=("tenant-slug", "processing"))
    conn = _Conn(tenant_cursor)
    chunker = MagicMock()
    chunker.chunk.return_value = [{"chunk_index": 0, "text": "content"}]
    indexer = MagicMock()
    events = []

    with (
        patch("api.db.get_conn", return_value=conn),
        patch("ingestion.queue.heartbeat_job", side_effect=lambda job_id, conn: events.append("heartbeat")) as heartbeat_job,
        patch("ingestion.queue.complete_job", side_effect=lambda job_id, conn: events.append("complete")) as complete_job,
        patch("ingestion.queue.fail_job") as fail_job,
        patch("ingestion.parser.parse_document", side_effect=lambda path: events.append("parse") or "content"),
        patch("ingestion.chunker.TurkishChunker", return_value=chunker),
        patch("ingestion.indexer.TenantIndexer", return_value=indexer),
    ):
        _process_job({
            "id": "job-1",
            "tenant_id": "tenant-1",
            "document_id": "doc-1",
            "filename": "file.txt",
            "file_path": "/tmp/file.txt",
        })

    assert events == ["heartbeat", "parse", "complete"]
    heartbeat_job.assert_called_once()
    indexer.ingest.assert_called_once_with("doc-1", "tenant-slug", "file.txt", [{"chunk_index": 0, "text": "content"}])
    complete_job.assert_called_once()
    fail_job.assert_not_called()


def test_process_job_marks_document_error_after_retry_exhaustion():
    from ingestion.worker import _process_job

    tenant_cursor = _Cursor(fetchone_result=("tenant-slug", "processing"))
    conn = _Conn(tenant_cursor)
    events = []

    with (
        patch("api.db.get_conn", return_value=conn),
        patch("ingestion.queue.heartbeat_job", side_effect=lambda job_id, conn: events.append("heartbeat")),
        patch("ingestion.queue.complete_job") as complete_job,
        patch(
            "ingestion.queue.fail_job",
            side_effect=lambda job_id, error, conn: events.append("fail") or {"status": "failed"},
        ) as fail_job,
        patch("ingestion.parser.parse_document", side_effect=RuntimeError("parse failed")),
        patch("ingestion.worker._mark_document_error") as mark_document_error,
    ):
        _process_job({
            "id": "job-1",
            "tenant_id": "tenant-1",
            "document_id": "doc-1",
            "filename": "file.txt",
            "file_path": "/tmp/file.txt",
        })

    assert events == ["heartbeat", "fail"]
    fail_job.assert_called_once()
    complete_job.assert_not_called()
    mark_document_error.assert_called_once_with("doc-1")


def test_process_job_completes_already_ready_document_without_reingesting():
    from ingestion.worker import _process_job

    tenant_cursor = _Cursor(fetchone_result=("tenant-slug", "ready"))
    conn = _Conn(tenant_cursor)

    with (
        patch("api.db.get_conn", return_value=conn),
        patch("ingestion.queue.complete_job") as complete_job,
        patch("ingestion.queue.fail_job") as fail_job,
        patch("ingestion.parser.parse_document") as parse_document,
        patch("ingestion.indexer.TenantIndexer") as tenant_indexer,
    ):
        _process_job({
            "id": "job-1",
            "tenant_id": "tenant-1",
            "document_id": "doc-1",
            "filename": "file.txt",
            "file_path": "/tmp/file.txt",
        })

    complete_job.assert_called_once()
    fail_job.assert_not_called()
    parse_document.assert_not_called()
    tenant_indexer.assert_not_called()


def test_active_job_heartbeat_stops_after_success():
    from ingestion.worker import _active_job_heartbeat

    heartbeat = MagicMock()

    with (
        patch("ingestion.worker._JobHeartbeat", return_value=heartbeat),
        _active_job_heartbeat("job-1"),
    ):
        pass

    heartbeat.start.assert_called_once()
    heartbeat.stop.assert_called_once()


def test_active_job_heartbeat_stops_after_failure():
    from ingestion.worker import _active_job_heartbeat

    heartbeat = MagicMock()

    with (
        patch("ingestion.worker._JobHeartbeat", return_value=heartbeat),
        patch("ingestion.worker.logger"),
    ):
        try:
            with _active_job_heartbeat("job-1"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass

    heartbeat.start.assert_called_once()
    heartbeat.stop.assert_called_once()


def test_heartbeat_update_errors_do_not_fail_ingestion_job():
    from ingestion.worker import _process_job

    tenant_cursor = _Cursor(fetchone_result=("tenant-slug", "processing"))
    conn = _Conn(tenant_cursor)
    chunker = MagicMock()
    chunker.chunk.return_value = [{"chunk_index": 0, "text": "content"}]
    indexer = MagicMock()

    with (
        patch("api.db.get_conn", return_value=conn),
        patch("ingestion.queue.heartbeat_job", side_effect=RuntimeError("heartbeat failed")),
        patch("ingestion.queue.complete_job") as complete_job,
        patch("ingestion.queue.fail_job") as fail_job,
        patch("ingestion.parser.parse_document", return_value="content"),
        patch("ingestion.chunker.TurkishChunker", return_value=chunker),
        patch("ingestion.indexer.TenantIndexer", return_value=indexer),
        patch("ingestion.worker.logger") as logger,
    ):
        _process_job({
            "id": "job-1",
            "tenant_id": "tenant-1",
            "document_id": "doc-1",
            "filename": "file.txt",
            "file_path": "/tmp/file.txt",
        })

    logger.warning.assert_called()
    complete_job.assert_called_once()
    fail_job.assert_not_called()


@pytest.mark.parametrize(
    ("env_name", "module_name", "attr_name", "valid_value"),
    [
        ("INGESTION_MAX_JOB_ATTEMPTS", "ingestion.queue", "MAX_JOB_ATTEMPTS", "4"),
        ("INGESTION_RETRY_DELAY_SECONDS", "ingestion.queue", "RETRY_DELAY_SECONDS", "15"),
        ("INGESTION_STALE_JOB_TIMEOUT_SECONDS", "ingestion.queue", "STALE_JOB_TIMEOUT_SECONDS", "120"),
        ("INGESTION_POLL_INTERVAL_SECONDS", "ingestion.worker", "POLL_INTERVAL_SECONDS", "2"),
        ("INGESTION_HEARTBEAT_INTERVAL_SECONDS", "ingestion.worker", "HEARTBEAT_INTERVAL_SECONDS", "10"),
    ],
)
def test_ingestion_numeric_env_limits_fail_fast(monkeypatch, env_name, module_name, attr_name, valid_value):
    module = importlib.import_module(module_name)

    monkeypatch.setenv(env_name, "0")
    with pytest.raises(RuntimeError, match=f"{env_name} must be a positive integer"):
        importlib.reload(module)

    monkeypatch.setenv(env_name, valid_value)
    reloaded = importlib.reload(module)
    assert getattr(reloaded, attr_name) == int(valid_value)
