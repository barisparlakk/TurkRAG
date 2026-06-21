from unittest.mock import MagicMock, Mock, patch

from api.db import _PooledConnection


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
