"""Regression tests for document upload safety and queue behaviour."""

import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost/test_unused")
os.environ.setdefault("LLM_MODEL_PATH", "/dev/null")
os.environ.setdefault("TURKISH_EMBEDDER_PATH", "/dev/null")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import api.db as db_module
    import api.main as main_module
    import ingestion.worker as worker_module

    original = main_module._init_postgres
    original_get_pool = db_module._get_pool
    original_pool = db_module._pool
    original_start_worker = worker_module.start_worker
    original_stop_worker = worker_module.stop_worker

    main_module._init_postgres = lambda: None
    db_module._get_pool = lambda: None
    db_module._pool = None
    worker_module.start_worker = lambda: None
    worker_module.stop_worker = lambda: None
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    main_module._init_postgres = original
    db_module._get_pool = original_get_pool
    db_module._pool = original_pool
    worker_module.start_worker = original_start_worker
    worker_module.stop_worker = original_stop_worker


def _token(client):
    return client.post("/auth/token", json={
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "member-user",
    }).json()["access_token"]


class _Cursor:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if self.queries and "SELECT id FROM documents" in self.queries[-1][0] and self.duplicate:
            return ("existing-doc",)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, duplicate=False):
        self.cursor_obj = _Cursor(duplicate=duplicate)

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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
