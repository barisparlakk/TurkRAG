from unittest.mock import MagicMock, Mock, patch

import pytest

from api.db import _pool_bounds, _PooledConnection


def test_close_returns_connection_to_pool_once():
    raw_conn = Mock()
    pool = Mock()
    conn = _PooledConnection(raw_conn)

    with patch("api.db._get_pool", return_value=pool):
        conn.close()
        conn.close()

    pool.putconn.assert_called_once_with(raw_conn)


def test_close_stays_idempotent_when_pool_return_fails():
    raw_conn = Mock()
    pool = Mock()
    pool.putconn.side_effect = RuntimeError("pool unavailable")
    conn = _PooledConnection(raw_conn)

    with patch("api.db._get_pool", return_value=pool):
        conn.close()
        conn.close()

    pool.putconn.assert_called_once_with(raw_conn)


def test_proxy_delegates_attributes_and_context_manager():
    raw_conn = MagicMock()
    raw_conn.status = "ready"
    conn = _PooledConnection(raw_conn)

    assert conn.status == "ready"

    conn.autocommit = True
    assert raw_conn.autocommit is True

    with conn:
        pass

    raw_conn.__enter__.assert_called_once_with()
    raw_conn.__exit__.assert_called_once_with(None, None, None)


def test_pool_bounds_use_env_overrides(monkeypatch):
    monkeypatch.setenv("DB_POOL_MIN", "3")
    monkeypatch.setenv("DB_POOL_MAX", "12")

    assert _pool_bounds() == (3, 12)


@pytest.mark.parametrize(
    ("env_name", "env_value", "message"),
    [
        ("DB_POOL_MIN", "0", "DB_POOL_MIN must be at least 1"),
        ("DB_POOL_MAX", "0", "DB_POOL_MAX must be at least 1"),
        ("DB_POOL_MIN", "11", "DB_POOL_MIN must be less than or equal to DB_POOL_MAX"),
    ],
)
def test_pool_bounds_reject_invalid_values(monkeypatch, env_name, env_value, message):
    monkeypatch.setenv("DB_POOL_MIN", "2")
    monkeypatch.setenv("DB_POOL_MAX", "10")
    monkeypatch.setenv(env_name, env_value)

    with pytest.raises(RuntimeError, match=message):
        _pool_bounds()


def test_get_pool_uses_validated_bounds(monkeypatch):
    import api.db as db_module

    fake_pool = object()
    monkeypatch.setenv("DB_POOL_MIN", "4")
    monkeypatch.setenv("DB_POOL_MAX", "9")
    monkeypatch.setattr(db_module, "_pool", None)

    with patch("api.db.ThreadedConnectionPool", return_value=fake_pool) as pool_cls:
        pool = db_module._get_pool()

    assert pool is fake_pool
    pool_cls.assert_called_once_with(minconn=4, maxconn=9, dsn=db_module.POSTGRES_URL)
