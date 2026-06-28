"""Shared database connection pool.

Uses psycopg2 ThreadedConnectionPool so each request borrows a connection
instead of opening a new one. Pool size: 2–10 connections.

get_conn() returns a _PooledConnection proxy: all attribute access is
forwarded to the real connection, but .close() returns it to the pool
instead of closing it. All existing callers work with zero changes.
"""

import logging
import os

from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")

_pool: ThreadedConnectionPool | None = None


def _pool_bounds() -> tuple[int, int]:
    """Read and validate connection-pool limits from the environment."""
    minconn = int(os.getenv("DB_POOL_MIN", "2"))
    maxconn = int(os.getenv("DB_POOL_MAX", "10"))
    if minconn < 1:
        raise RuntimeError("DB_POOL_MIN must be at least 1")
    if maxconn < 1:
        raise RuntimeError("DB_POOL_MAX must be at least 1")
    if minconn > maxconn:
        raise RuntimeError("DB_POOL_MIN must be less than or equal to DB_POOL_MAX")
    return minconn, maxconn


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        minconn, maxconn = _pool_bounds()
        _pool = ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, dsn=POSTGRES_URL)
        logger.info("DB connection pool created (min=%d, max=%d)", minconn, maxconn)
    return _pool


class _PooledConnection:
    """Proxy that forwards everything to the real connection.
    .close() returns the connection to the pool instead of destroying it.
    """
    __slots__ = ("_conn",)

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def close(self):
        conn = object.__getattribute__(self, "_conn")
        if conn is None:
            return

        # Clear the handle first so repeated close calls cannot enqueue the
        # same physical connection more than once.
        object.__setattr__(self, "_conn", None)
        try:
            _get_pool().putconn(conn)
        except Exception as exc:
            logger.warning("Failed to return connection to pool: %s", exc)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_conn"), name, value)

    def __enter__(self):
        return object.__getattribute__(self, "_conn").__enter__()

    def __exit__(self, *args):
        return object.__getattribute__(self, "_conn").__exit__(*args)


def get_conn() -> _PooledConnection:
    """Borrow a connection from the pool.
    Call conn.close() when done — it returns to pool, not destroyed.
    """
    return _PooledConnection(_get_pool().getconn())
