"""API integration tests using FastAPI TestClient — no live DB or LLM required."""

import asyncio
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
    import api.routers.health as health_module
    import ingestion.worker as worker_module

    original = main_module._ensure_schema_ready
    original_get_pool = db_module._get_pool
    original_pool = db_module._pool
    original_check_qdrant = health_module._check_qdrant
    original_check_postgres = health_module._check_postgres
    original_start_worker = worker_module.start_worker
    original_stop_worker = worker_module.stop_worker

    main_module._ensure_schema_ready = lambda: None
    db_module._get_pool = lambda: None
    db_module._pool = None
    health_module._check_qdrant = lambda: "ok"
    health_module._check_postgres = lambda: "ok"
    worker_module.start_worker = lambda: None
    worker_module.stop_worker = lambda: None
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    main_module._ensure_schema_ready = original
    db_module._get_pool = original_get_pool
    db_module._pool = original_pool
    health_module._check_qdrant = original_check_qdrant
    health_module._check_postgres = original_check_postgres
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

        with (
            patch("api.auth.MOCK_ADMIN_EMAIL", "baris@dev.com"),
            patch("api.auth.MOCK_ADMIN_PASSWORD", "1234"),
            patch("api.db.get_conn", return_value=FakeConn()),
        ):
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
        with (
            patch("api.auth.MOCK_ADMIN_EMAIL", "baris@dev.com"),
            patch("api.auth.MOCK_ADMIN_PASSWORD", "1234"),
        ):
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

    def test_evaluation_endpoints_require_admin_token(self, client):
        member_token = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "member-user",
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {member_token}"}

        assert client.post("/eval/run", headers=headers).status_code == 403
        assert client.get("/eval/history", headers=headers).status_code == 403
        assert client.get("/eval/runs/job-1", headers=headers).status_code == 403

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

        with (
            patch("api.auth.MOCK_ADMIN_EMAIL", "baris@dev.com"),
            patch("api.auth.MOCK_ADMIN_PASSWORD", "1234"),
            patch("api.db.get_conn", return_value=FakeConn()),
        ):
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

    def test_login_accepts_active_user_credentials(self, client):
        from api.auth import hash_password

        class FakeCursor:
            def execute(self, query, params):
                self.params = params

            def fetchone(self):
                return (
                    "10000000-0000-0000-0000-000000000001",
                    "00000000-0000-0000-0000-000000000001",
                    "admin@acme.com",
                    hash_password("password123"),
                    "admin",
                    True,
                    "Acme Sirket",
                    "acme-sirket",
                )

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
            resp = client.post("/auth/login", json={
                "tenant_slug": "acme-sirket",
                "email": "admin@acme.com",
                "password": "password123",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant"]["slug"] == "acme-sirket"
        assert body["user"]["role"] == "admin"
        assert "access_token" in body

    def test_login_rejects_bad_password(self, client):
        from api.auth import hash_password

        class FakeCursor:
            def execute(self, query, params):
                pass

            def fetchone(self):
                return (
                    "10000000-0000-0000-0000-000000000001",
                    "00000000-0000-0000-0000-000000000001",
                    "admin@acme.com",
                    hash_password("password123"),
                    "admin",
                    True,
                    "Acme Sirket",
                    "acme-sirket",
                )

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
            resp = client.post("/auth/login", json={
                "tenant_slug": "acme-sirket",
                "email": "admin@acme.com",
                "password": "wrong-password",
            })

        assert resp.status_code == 401

    def test_dev_token_endpoint_returns_403_when_dev_auth_disabled(self, client):
        with patch("api.main.ENABLE_DEV_AUTH", False):
            resp = client.post("/auth/token", json={
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "user_id": "test",
            })

        assert resp.status_code == 403

    def test_mock_admin_login_returns_403_when_dev_auth_disabled(self, client):
        with patch("api.main.ENABLE_DEV_AUTH", False):
            resp = client.post("/auth/mock-login", json={
                "tenant_slug": "acme-sirket",
                "email": "baris@dev.com",
                "password": "1234",
            })

        assert resp.status_code == 403

    def test_validate_mock_admin_returns_false_without_configured_credentials(self):
        from api.auth import validate_mock_admin

        with (
            patch("api.auth.MOCK_ADMIN_EMAIL", ""),
            patch("api.auth.MOCK_ADMIN_PASSWORD", ""),
        ):
            assert validate_mock_admin("baris@dev.com", "1234") is False

    def test_production_startup_rejects_dev_auth(self):
        import api.main as main_module

        async def _start():
            async with main_module.lifespan(main_module.app):
                pass

        with (
            patch("api.main.APP_ENV", "production"),
            patch("api.main.ENABLE_DEV_AUTH", True),
            patch.dict(os.environ, {"JWT_SECRET": "test-secret"}, clear=False),
            pytest.raises(RuntimeError, match="ENABLE_DEV_AUTH"),
        ):
            asyncio.run(_start())

    def test_non_development_startup_rejects_dev_auth(self):
        import api.main as main_module

        async def _start():
            async with main_module.lifespan(main_module.app):
                pass

        with (
            patch("api.main.APP_ENV", "staging"),
            patch("api.main.ENABLE_DEV_AUTH", True),
            patch.dict(os.environ, {"JWT_SECRET": "test-secret"}, clear=False),
            pytest.raises(RuntimeError, match="only allowed"),
        ):
            asyncio.run(_start())


class TestTenantEndpointAuth:
    def test_tenants_without_token_returns_401_or_403(self, client):
        assert client.get("/tenants").status_code in (401, 403, 422)

    def test_tenant_admin_cannot_list_global_tenants(self, client):
        from api.auth import create_token

        token = create_token(
            tenant_id="00000000-0000-0000-0000-000000000001",
            user_id="admin-user",
            role="admin",
            email="admin@example.com",
            dev=True,
        )

        resp = client.get("/tenants", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 403

    def test_platform_admin_can_list_global_tenants(self, client):
        from api.auth import create_token

        class FakeCursor:
            def execute(self, query, params=None):
                pass

            def fetchall(self):
                return [("00000000-0000-0000-0000-000000000001", "Acme", "acme", "2026-06-24T00:00:00Z")]

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        token = create_token(
            tenant_id="00000000-0000-0000-0000-000000000001",
            user_id="platform-admin",
            role="platform_admin",
            email="platform@example.com",
            dev=True,
        )

        with patch("api.routers.tenants.get_conn", return_value=FakeConn()):
            resp = client.get("/tenants", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        assert resp.json()[0]["slug"] == "acme"


class TestChatWebSocketValidation:
    def test_websocket_rejects_invalid_top_k_before_auth(self, client):
        with client.websocket_connect("/chat/stream") as websocket:
            websocket.send_json({"query": "Merhaba", "token": "bad-token", "top_k": 999})
            frame = websocket.receive_json()

        assert frame == {"type": "error", "message": "Invalid message"}

    def test_websocket_suppresses_auth_exception_details(self, client):
        with client.websocket_connect("/chat/stream") as websocket:
            websocket.send_json({"query": "Merhaba", "token": "bad-token", "top_k": 5})
            frame = websocket.receive_json()

        assert frame == {"type": "error", "message": "Authentication failed"}


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


class TestDocumentPermissions:
    def test_member_document_list_only_returns_accessible_rows(self, client):
        token = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "member-user",
        }).json()["access_token"]

        class FakeCursor:
            def execute(self, query, params):
                self.query = query

            def fetchall(self):
                if "SELECT d.id" in self.query:
                    return [("doc-visible",)]
                if "id = ANY" in self.query:
                    return [("doc-visible", "Visible.txt", 4, "ready", "2026-06-15T00:00:00Z")]
                return []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        with patch("api.routers.documents.get_conn", return_value=FakeConn()):
            resp = client.get("/documents", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        assert resp.json() == [
            {
                "id": "doc-visible",
                "filename": "Visible.txt",
                "chunk_count": 4,
                "status": "ready",
                "created_at": "2026-06-15T00:00:00Z",
            }
        ]

    def test_member_cannot_grant_permissions_without_owner_access(self, client):
        token = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "member-user",
        }).json()["access_token"]

        class FakeCursor:
            def execute(self, query, params):
                self.query = query

            def fetchone(self):
                if "SELECT id FROM documents" in self.query:
                    return ("doc-1",)
                if "SELECT permission_level FROM document_permissions" in self.query:
                    return None
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

        with patch("api.routers.permissions.get_conn", return_value=FakeConn()):
            resp = client.post(
                "/documents/doc-1/permissions",
                json={"user_id": "other-user", "level": "viewer"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 403
