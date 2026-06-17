"""Tests for tenant admin bootstrap helper."""

from scripts.bootstrap_admin import bootstrap_admin_user


class _Cursor:
    def __init__(self, fetches):
        self.fetches = list(fetches)
        self.executed = []

    def execute(self, query, params):
        self.executed.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.fetches.pop(0)

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


def test_bootstrap_admin_creates_missing_user():
    cursor = _Cursor(
        fetches=[
            ("tenant-1", "Acme", "acme"),
            None,
            ("user-1",),
        ]
    )
    conn = _Conn(cursor)

    summary = bootstrap_admin_user(
        conn,
        tenant_slug="acme",
        email="ADMIN@ACME.COM",
        password="secret123",
    )

    assert summary["action"] == "created"
    assert summary["email"] == "admin@acme.com"
    assert summary["user_id"] == "user-1"
    assert conn.committed is True
    assert conn.rolled_back is False
    assert any("INSERT INTO users" in query for query, _ in cursor.executed)


def test_bootstrap_admin_updates_existing_inactive_member():
    cursor = _Cursor(
        fetches=[
            ("tenant-1", "Acme", "acme"),
            ("user-9", "member", False),
        ]
    )
    conn = _Conn(cursor)

    summary = bootstrap_admin_user(
        conn,
        tenant_slug="acme",
        email="member@acme.com",
        password="secret123",
    )

    assert summary["action"] == "updated"
    assert summary["previous_role"] == "member"
    assert summary["was_active"] is False
    assert conn.committed is True
    assert any("UPDATE users" in query for query, _ in cursor.executed)


def test_bootstrap_admin_dry_run_rolls_back_without_writes():
    cursor = _Cursor(
        fetches=[
            ("tenant-1", "Acme", "acme"),
            ("user-9", "admin", True),
        ]
    )
    conn = _Conn(cursor)

    summary = bootstrap_admin_user(
        conn,
        tenant_slug="acme",
        email="admin@acme.com",
        password="secret123",
        dry_run=True,
    )

    assert summary["action"] == "unchanged"
    assert conn.committed is False
    assert conn.rolled_back is True
    assert all("UPDATE users" not in query and "INSERT INTO users" not in query for query, _ in cursor.executed)
