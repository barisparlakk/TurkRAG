"""API integration tests using FastAPI TestClient — no live DB or LLM required."""

import os
from unittest.mock import patch

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


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_response_has_status_field(self, client):
        assert "status" in client.get("/health").json()

    def test_health_status_is_string(self, client):
        assert isinstance(client.get("/health").json()["status"], str)


class TestAuthEndpoint:
    def test_token_endpoint_exists(self, client):
        resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "test",
        })
        assert resp.status_code == 200

    def test_token_endpoint_returns_member_access_token_on_success(self, client):
        resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "test",
        })
        assert "access_token" in resp.json()

    def test_token_endpoint_rejects_missing_user_id(self, client):
        resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
        })
        assert resp.status_code == 422

    def test_mock_admin_login_accepts_expected_credentials(self, client):
        class FakeCursor:
            def execute(self, query, params):
                self.slug = params[0]

            def fetchone(self):
                if self.slug == "acme-sirket":
                    return ("00000000-0000-0000-0000-000000000001", "Acme Sirket", "acme-sirket")
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        with patch("api.db.get_conn", return_value=FakeConn()):
            resp = client.post("/auth/mock-login", json={
                "tenant_slug": "acme-sirket",
                "email": "baris@dev.com",
                "password": "1234",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["role"] == "admin"
        assert body["user"]["email"] == "baris@dev.com"
        assert body["tenant"]["slug"] == "acme-sirket"
        assert "access_token" in body

    def test_mock_admin_login_rejects_wrong_password(self, client):
        resp = client.post("/auth/mock-login", json={
            "tenant_slug": "acme-sirket",
            "email": "baris@dev.com",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_admin_switch_tenant_requires_admin_token(self, client):
        member_token = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "member-user",
        }).json()["access_token"]

        resp = client.post(
            "/auth/admin/switch-tenant",
            json={"tenant_slug": "acme-sirket"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert resp.status_code == 403

    def test_admin_switch_tenant_returns_new_admin_token(self, client):
        class FakeCursor:
            def execute(self, query, params):
                self.slug = params[0]

            def fetchone(self):
                if self.slug == "acme-sirket":
                    return ("00000000-0000-0000-0000-000000000001", "Acme Sirket", "acme-sirket")
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        with patch("api.db.get_conn", return_value=FakeConn()):
            admin_token = client.post("/auth/mock-login", json={
                "tenant_slug": "acme-sirket",
                "email": "baris@dev.com",
                "password": "1234",
            }).json()["access_token"]
            resp = client.post(
                "/auth/admin/switch-tenant",
                json={"tenant_slug": "acme-sirket"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["role"] == "admin"
        assert body["tenant"]["slug"] == "acme-sirket"
        assert "access_token" in body


class TestTenantEndpointAuth:
    def test_tenants_without_token_returns_401_or_403(self, client):
        assert client.get("/tenants").status_code in (401, 403, 422)


class TestChatEndpointAuth:
    def test_chat_without_token_returns_401_or_403(self, client):
        assert client.post("/chat", json={"query": "test sorusu"}).status_code in (401, 403, 422)

    def test_documents_without_token_returns_401_or_403(self, client):
        assert client.get("/documents").status_code in (401, 403, 422)

    def test_analytics_without_token_returns_401_or_403(self, client):
        assert client.get("/analytics/stats").status_code in (401, 403, 422)


class TestDocumentUploadValidation:
    def test_unsupported_extension_rejected(self, client):
        from io import BytesIO
        resp = client.post(
            "/documents/upload",
            files={"file": ("test.exe", BytesIO(b"bad"), "application/octet-stream")},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code in (401, 403, 422)

    def test_unsupported_extension_returns_422_with_valid_token(self, client):
        from io import BytesIO
        # /auth/token doesn't hit the DB — any UUID-like tenant_id works
        token_resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "test",
        })
        if token_resp.status_code != 200:
            pytest.skip("Token endpoint unavailable")
        token = token_resp.json()["access_token"]

        resp = client.post(
            "/documents/upload",
            files={"file": ("malware.exe", BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422
        assert ".exe" in resp.json().get("detail", "").lower() or "unsupported" in resp.json().get("detail", "").lower()
