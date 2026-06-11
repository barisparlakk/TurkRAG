"""Middleware unit tests."""

from api.middleware import _get_cors_origins


class TestCorsOrigins:
    def test_defaults_to_wildcard_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        assert _get_cors_origins() == ["*"]

    def test_empty_env_falls_back_to_wildcard(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "   ")
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
