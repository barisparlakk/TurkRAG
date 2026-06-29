"""Regression tests for document upload safety and queue behaviour."""

import asyncio
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost/test_unused")
os.environ.setdefault("LLM_MODEL_PATH", "/dev/null")
os.environ.setdefault("TURKISH_EMBEDDER_PATH", "/dev/null")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import api.db as db_module
    import api.main as main_module
    import ingestion.worker as worker_module

    original = main_module._ensure_schema_ready
    original_get_pool = db_module._get_pool
    original_pool = db_module._pool
    original_start_worker = worker_module.start_worker
    original_stop_worker = worker_module.stop_worker

    main_module._ensure_schema_ready = lambda: None
    db_module._get_pool = lambda: None
    db_module._pool = None
    worker_module.start_worker = lambda: None
    worker_module.stop_worker = lambda: None
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    main_module._ensure_schema_ready = original
    db_module._get_pool = original_get_pool
    db_module._pool = original_pool
    worker_module.start_worker = original_start_worker
    worker_module.stop_worker = original_stop_worker


def _token(client):
    return client.post("/auth/token", json={
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "member-user",
    }).json()["access_token"]


class _DbState:
    def __init__(self, duplicate=False, raise_on_insert=False, raise_on_delete=False):
        self.duplicate = duplicate
        self.raise_on_insert = raise_on_insert
        self.raise_on_delete = raise_on_delete
        self.queries = []


class _Cursor:
    def __init__(self, state):
        self.state = state

    def execute(self, query, params=None):
        self.state.queries.append((query, params))
        if "INSERT INTO documents" in query and self.state.raise_on_insert:
            raise RuntimeError("insert failed")
        if "DELETE FROM documents" in query and self.state.raise_on_delete:
            raise RuntimeError("delete failed")

    def fetchone(self):
        if self.state.queries and "SELECT id FROM documents" in self.state.queries[-1][0] and self.state.duplicate:
            return ("existing-doc",)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, state=None, duplicate=False, raise_on_insert=False, raise_on_delete=False):
        self.state = state or _DbState(
            duplicate=duplicate,
            raise_on_insert=raise_on_insert,
            raise_on_delete=raise_on_delete,
        )
        self.cursor_obj = _Cursor(self.state)

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _delete_queries(state):
    return [query for query, _ in state.queries if "DELETE FROM documents" in query]


def _job_row(job_id="job-1", tenant_id="tenant-1", document_id="doc-1", filename="sample.txt"):
    return (
        job_id,
        tenant_id,
        document_id,
        filename,
        "pending",
        None,
        "2026-06-29T10:00:00",
        None,
        None,
        0,
        3,
        None,
        None,
    )


def test_upload_enqueues_once_and_does_not_run_inline_ingestion(client, tmp_path):
    token = _token(client)
    cache = MagicMock()

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn()),
        patch("api.routers.documents.grant_access"),
        patch("retrieval.semantic_cache.get_cache", return_value=cache),
        patch("ingestion.queue.enqueue_job", return_value="job-1") as enqueue_job,
        patch("api.routers.documents._ingest_document") as ingest_document,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("sample.txt", BytesIO(b"hello world"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] == "job-1"
    assert body["filename"] == "sample.txt"
    enqueue_job.assert_called_once()
    ingest_document.assert_not_called()


def test_upload_streams_file_and_sanitizes_filename(client, tmp_path):
    token = _token(client)
    content = b"streamed document"

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn()),
        patch("api.routers.documents.grant_access"),
        patch("retrieval.semantic_cache.get_cache", return_value=MagicMock()),
        patch("ingestion.queue.enqueue_job", return_value="job-2"),
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("../unsafe.txt", BytesIO(content), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["filename"] == "unsafe.txt"
    saved = tmp_path / f"{body['document_id']}.txt"
    assert saved.read_bytes() == content
    assert not list(tmp_path.glob("*.tmp"))


def test_upload_rejects_over_limit_and_cleans_temp_file(client, tmp_path):
    token = _token(client)

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.MAX_UPLOAD_BYTES", 4),
        patch("api.routers.documents.get_conn") as get_conn,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("large.txt", BytesIO(b"12345"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 413
    get_conn.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_duplicate_upload_returns_409_and_does_not_enqueue(client, tmp_path):
    token = _token(client)

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn(duplicate=True)),
        patch("ingestion.queue.enqueue_job") as enqueue_job,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("duplicate.txt", BytesIO(b"same"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 409
    enqueue_job.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_db_insert_failure_cleans_temp_file(client, tmp_path):
    token = _token(client)
    state = _DbState(raise_on_insert=True)

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn(state=state)),
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("insert-fails.txt", BytesIO(b"content"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 500
    assert list(tmp_path.iterdir()) == []
    assert _delete_queries(state) == []


def test_grant_access_failure_cleans_files_and_deletes_document_row(client, tmp_path):
    token = _token(client)
    state = _DbState()

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn(state=state)),
        patch("api.routers.documents.grant_access", side_effect=RuntimeError("acl failed")),
        patch("ingestion.queue.enqueue_job") as enqueue_job,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("acl-fails.txt", BytesIO(b"content"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 500
    enqueue_job.assert_not_called()
    assert list(tmp_path.iterdir()) == []
    assert len(_delete_queries(state)) == 1


def test_enqueue_failure_removes_final_file_and_deletes_document_row(client, tmp_path):
    token = _token(client)
    state = _DbState()

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn", return_value=_Conn(state=state)),
        patch("api.routers.documents.grant_access"),
        patch("retrieval.semantic_cache.get_cache", return_value=MagicMock()),
        patch("ingestion.queue.enqueue_job", side_effect=RuntimeError("queue down")),
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("queue-fails.txt", BytesIO(b"content"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 500
    assert list(tmp_path.iterdir()) == []
    assert len(_delete_queries(state)) == 1


def test_unsupported_extension_rejected_before_file_write(client, tmp_path):
    token = _token(client)

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn") as get_conn,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": ("malware.exe", BytesIO(b"MZ"), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 422
    get_conn.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_extension_only_filename_rejected_before_file_write(client, tmp_path):
    token = _token(client)

    with (
        patch("api.routers.documents.UPLOAD_DIR", tmp_path),
        patch("api.routers.documents.get_conn") as get_conn,
    ):
        resp = client.post(
            "/documents/upload",
            files={"file": (".txt", BytesIO(b"nameless"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Uploaded file must have a valid filename"
    get_conn.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_upload_filename_sanitizer_requires_usable_basename():
    from api.routers.documents import _sanitize_upload_filename

    assert _sanitize_upload_filename("../safe.txt") == ("safe.txt", ".txt")
    with pytest.raises(HTTPException) as exc:
        _sanitize_upload_filename(".pdf")

    assert exc.value.status_code == 422
    assert exc.value.detail == "Uploaded file must have a valid filename"


def test_job_status_denies_member_without_document_access():
    from api.routers import documents

    conn = _Conn()
    job = {
        "id": "job-1",
        "tenant_id": "tenant-1",
        "document_id": "doc-1",
        "filename": "sample.txt",
        "status": "pending",
    }

    with (
        patch("api.routers.documents.get_conn", return_value=conn),
        patch("ingestion.queue.get_job_status", return_value=job),
        patch("api.routers.documents.user_has_document_access", return_value=False),
        pytest.raises(HTTPException) as exc,
    ):
        asyncio.run(documents.get_job_status("job-1", {
            "id": "member-1",
            "tenant_id": "tenant-1",
            "role": "member",
        }))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Document access required"


def test_job_status_allows_admin_without_acl_check():
    from api.routers import documents

    job = {
        "id": "job-1",
        "tenant_id": "tenant-1",
        "document_id": "doc-1",
        "filename": "sample.txt",
        "status": "pending",
    }

    with (
        patch("api.routers.documents.get_conn", return_value=_Conn()),
        patch("ingestion.queue.get_job_status", return_value=job),
        patch("api.routers.documents.user_has_document_access") as user_has_document_access,
    ):
        result = asyncio.run(documents.get_job_status("job-1", {
            "id": "admin-1",
            "tenant_id": "tenant-1",
            "role": "admin",
        }))

    assert result == job
    user_has_document_access.assert_not_called()


def test_job_history_filters_member_to_accessible_documents():
    from api.routers import documents

    state = _DbState()
    rows = [_job_row(document_id="doc-1")]

    class JobsCursor(_Cursor):
        def fetchall(self):
            return rows

    class JobsConn(_Conn):
        def __init__(self):
            super().__init__(state=state)
            self.cursor_obj = JobsCursor(state)

    with (
        patch("api.routers.documents.get_conn", return_value=JobsConn()),
        patch("api.routers.documents.get_accessible_document_ids", return_value=["doc-1"]),
    ):
        result = asyncio.run(documents.list_jobs(limit=10, user={
            "id": "member-1",
            "tenant_id": "tenant-1",
            "role": "member",
        }))

    assert [job["document_id"] for job in result] == ["doc-1"]
    assert "document_id = ANY(%s)" in state.queries[-1][0]
    assert state.queries[-1][1] == ("tenant-1", ["doc-1"], 10)


def test_job_history_returns_empty_for_member_without_accessible_documents():
    from api.routers import documents

    get_conn = MagicMock(return_value=_Conn())

    with (
        patch("api.routers.documents.get_conn", get_conn),
        patch("api.routers.documents.get_accessible_document_ids", return_value=[]),
    ):
        result = asyncio.run(documents.list_jobs(limit=10, user={
            "id": "member-1",
            "tenant_id": "tenant-1",
            "role": "member",
        }))

    assert result == []
    assert get_conn.return_value.state.queries == []
