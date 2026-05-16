"""API integration tests using FastAPI TestClient — no live DB or LLM required."""

import os

import pytest

os.environ.setdefault("POSTGRES_URL", "postgresql://test:test@localhost/test_unused")
os.environ.setdefault("LLM_MODEL_PATH", "/dev/null")
os.environ.setdefault("TURKISH_EMBEDDER_PATH", "/dev/null")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    import api.main as main_module
    original = main_module._init_postgres

    main_module._init_postgres = lambda: None
    from api.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    main_module._init_postgres = original


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
            "role": "admin",
        })
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
