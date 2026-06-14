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


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=POSTGRES_URL)
        logger.info("DB connection pool created (min=2, max=10)")
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
