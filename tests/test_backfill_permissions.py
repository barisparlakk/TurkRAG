"""Tests for legacy document permission backfill."""

from scripts.backfill_document_permissions import (
    BACKFILL_SQL,
    backfill_document_permissions,
)


class _Cursor:
    def __init__(self, counts, rowcount=0):
        self.counts = list(counts)
        self.rowcount = rowcount
        self.queries = []

    def execute(self, query):
        self.queries.append(query)

    def fetchone(self):
        return (self.counts.pop(0),)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_backfill_document_permissions_writes_candidate_acls():
    cursor = _Cursor(counts=[7, 1], rowcount=7)
    conn = _Conn(cursor)

    summary = backfill_document_permissions(conn)

    assert summary == {
        "candidate_rows": 7,
        "inserted_rows": 7,
        "skipped_documents_without_active_users": 1,
    }
    assert cursor.queries[-1] == BACKFILL_SQL
    assert conn.committed is True
    assert conn.rolled_back is False


def test_backfill_document_permissions_dry_run_does_not_write():
    cursor = _Cursor(counts=[3, 0])
    conn = _Conn(cursor)

    summary = backfill_document_permissions(conn, dry_run=True)

    assert summary["candidate_rows"] == 3
    assert summary["inserted_rows"] == 0
    assert BACKFILL_SQL not in cursor.queries
    assert conn.committed is False
    assert conn.rolled_back is True
