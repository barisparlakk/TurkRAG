"""Middleware unit tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware import _get_cors_origins, setup_middleware


class TestCorsOrigins:
    def test_defaults_to_wildcard_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        monkeypatch.delenv("APP_ENV", raising=False)
        assert _get_cors_origins() == ["*"]

    def test_empty_env_falls_back_to_wildcard(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "   ")
        monkeypatch.delenv("APP_ENV", raising=False)
        assert _get_cors_origins() == ["*"]

    def test_comma_separated_origins_are_trimmed(self, monkeypatch):
        monkeypatch.setenv(
            "CORS_ORIGINS",
            "https://dashboard.example.com, http://localhost:5173 ,https://admin.example.com",
        )
        assert _get_cors_origins() == [
            "https://dashboard.example.com",
            "http://localhost:5173",
            "https://admin.example.com",
        ]

    def test_production_requires_explicit_cors_origins(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "   ")

        try:
            _get_cors_origins()
        except RuntimeError as exc:
            assert "CORS_ORIGINS must be set" in str(exc)
        else:
            raise AssertionError("Expected production CORS validation error")

    def test_production_rejects_wildcard_cors_origin(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "*")

        try:
            _get_cors_origins()
        except RuntimeError as exc:
            assert "CORS_ORIGINS='*' is not allowed" in str(exc)
        else:
            raise AssertionError("Expected wildcard CORS validation error")

    def test_middleware_sets_cors_header_for_allowed_origin(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("CORS_ORIGINS", "https://dashboard.example.com")

        app = FastAPI()

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        setup_middleware(app)
        client = TestClient(app)

        response = client.get(
            "/ping",
            headers={"Origin": "https://dashboard.example.com"},
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://dashboard.example.com"
