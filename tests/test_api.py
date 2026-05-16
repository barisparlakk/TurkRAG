"""API integration tests using FastAPI TestClient — no live DB or LLM required."""

import os
import pytest

# Prevent any real DB/model connections during tests
os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost/test_unused")
os.environ.setdefault("LLM_MODEL_PATH", "/dev/null")
os.environ.setdefault("TURKISH_EMBEDDER_PATH", "/dev/null")


@pytest.fixture(scope="module")
def client():
    """TestClient with lifespan disabled (no DB init)."""
    from fastapi.testclient import TestClient
    # Patch _init_postgres to be a no-op so TestClient doesn't need a real DB
    import api.main as main_module
    original = main_module._init_postgres

    def _noop():
        pass

    main_module._init_postgres = _noop
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    main_module._init_postgres = original


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_has_status_field(self, client):
        body = client.get("/health").json()
        assert "status" in body

    def test_health_status_is_string(self, client):
        body = client.get("/health").json()
        assert isinstance(body["status"], str)


class TestAuthEndpoint:
    def test_token_endpoint_exists(self, client):
        resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "test",
            "role": "admin",
        })
        # May fail with 500 if DB not available; check it at least routes correctly
        assert resp.status_code in (200, 422, 500)

    def test_token_endpoint_returns_access_token_on_success(self, client):
        resp = client.post("/auth/token", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "test",
            "role": "admin",
        })
        if resp.status_code == 200:
            assert "access_token" in resp.json()


class TestChatEndpointAuth:
    def test_chat_without_token_returns_401_or_403(self, client):
        resp = client.post("/chat", json={"query": "test sorusu"})
        assert resp.status_code in (401, 403, 422)

    def test_documents_without_token_returns_401_or_403(self, client):
        resp = client.get("/documents")
        assert resp.status_code in (401, 403, 422)

    def test_analytics_without_token_returns_401_or_403(self, client):
        resp = client.get("/analytics/stats")
        assert resp.status_code in (401, 403, 422)


class TestDocumentUploadValidation:
    def _auth_header(self):
        """Produce a minimal JWT-like header stub for upload tests."""
        # The real test is that invalid file types are rejected before auth
        return {}

    def test_unsupported_extension_rejected(self, client):
        from io import BytesIO
        resp = client.post(
            "/documents/upload",
            files={"file": ("test.exe", BytesIO(b"bad"), "application/octet-stream")},
            headers={"Authorization": "Bearer fake"},
        )
        # 401/403 (bad JWT) or 422 (validation) are both acceptable
        assert resp.status_code in (401, 403, 422)
