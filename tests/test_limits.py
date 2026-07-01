"""Rate-limit keying tests."""

from types import SimpleNamespace

from api.limits import _ws_hits, rate_limit_key, websocket_rate_key, websocket_rate_limited


class _WebSocket:
    def __init__(self, host="127.0.0.1"):
        self.client = SimpleNamespace(host=host)


class _Request:
    def __init__(self, auth_header="", host="127.0.0.1"):
        self.headers = {"Authorization": auth_header} if auth_header else {}
        self.client = SimpleNamespace(host=host)
        self.scope = {"client": (host, 12345)}


def test_rate_limit_key_uses_tenant_and_user_claims(monkeypatch):
    monkeypatch.setattr(
        "api.auth.decode_token",
        lambda token: {"tenant_id": "tenant-1", "user_id": "user-1"},
    )

    key = rate_limit_key(_Request("Bearer token"))

    assert key == "tenant:tenant-1:user:user-1"


def test_rate_limit_key_handles_legacy_tenant_only_claims(monkeypatch):
    monkeypatch.setattr("api.auth.decode_token", lambda token: {"tenant_id": "tenant-1"})

    key = rate_limit_key(_Request("Bearer token"))

    assert key == "tenant:tenant-1:user:anonymous"


def test_rate_limit_key_falls_back_to_client_for_invalid_token(monkeypatch):
    def raise_invalid_token(token):
        raise ValueError("invalid")

    monkeypatch.setattr("api.auth.decode_token", raise_invalid_token)

    assert rate_limit_key(_Request("Bearer bad-token", host="10.0.0.5")) == "10.0.0.5"


def test_websocket_rate_key_uses_tenant_and_user():
    key = websocket_rate_key({
        "tenant_id": "tenant-1",
        "id": "user-1",
    })

    assert key == "tenant:tenant-1:user:user-1"


def test_websocket_rate_key_falls_back_for_missing_claims():
    assert websocket_rate_key({}) == "tenant:unknown-tenant:user:anonymous"


def test_websocket_rate_limited_separates_users_in_same_tenant():
    _ws_hits.clear()
    websocket = _WebSocket()

    assert websocket_rate_limited(websocket, "tenant:t1:user:u1", limit=1, window_seconds=60) is False
    assert websocket_rate_limited(websocket, "tenant:t1:user:u1", limit=1, window_seconds=60) is True
    assert websocket_rate_limited(websocket, "tenant:t1:user:u2", limit=1, window_seconds=60) is False


def test_websocket_rate_limited_expires_old_hits(monkeypatch):
    _ws_hits.clear()
    websocket = _WebSocket()
    times = iter([100.0, 170.0])

    monkeypatch.setattr("api.limits.time.monotonic", lambda: next(times))

    assert websocket_rate_limited(websocket, "tenant:t1:user:u1", limit=1, window_seconds=60) is False
    assert websocket_rate_limited(websocket, "tenant:t1:user:u1", limit=1, window_seconds=60) is False
