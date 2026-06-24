"""Startup schema verification tests."""

from unittest.mock import patch

import pytest


class _Cursor:
    def __init__(self, version_table=True, revision="0003_acl_backfill", tables=None):
        self.version_table = version_table
        self.revision = revision
        self.tables = tables or {
            "tenants",
            "documents",
            "users",
            "sessions",
            "messages",
            "query_logs",
            "document_permissions",
            "eval_runs",
            "ingestion_jobs",
            "document_versions",
        }
        self.query = ""

    def execute(self, query, params=None):
        self.query = query

    def fetchone(self):
        if "to_regclass" in self.query:
            return ("alembic_version",) if self.version_table else (None,)
        if "version_num" in self.query:
            return (self.revision,) if self.revision else None
        return None

    def fetchall(self):
        if "information_schema.tables" in self.query:
            return [(table,) for table in sorted(self.tables)]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def cursor(self):
        return self.cursor_obj

    def close(self):
        return None


def test_schema_verification_passes_at_required_revision():
    import api.main as main_module

    with (
        patch("api.main.AUTO_INIT_SCHEMA", False),
        patch("psycopg2.connect", return_value=_Conn(_Cursor())),
    ):
        main_module._ensure_schema_ready()


def test_schema_verification_passes_at_legacy_revision_alias():
    import api.main as main_module

    with (
        patch("api.main.AUTO_INIT_SCHEMA", False),
        patch(
            "psycopg2.connect",
            return_value=_Conn(_Cursor(revision="0003_backfill_document_permissions")),
        ),
    ):
        main_module._ensure_schema_ready()


def test_schema_verification_fails_without_alembic_version_table():
    import api.main as main_module

    with (
        patch("api.main.AUTO_INIT_SCHEMA", False),
        patch("psycopg2.connect", return_value=_Conn(_Cursor(version_table=False))),
        pytest.raises(RuntimeError, match="alembic upgrade head"),
    ):
        main_module._ensure_schema_ready()


def test_schema_verification_fails_on_revision_mismatch():
    import api.main as main_module

    with (
        patch("api.main.AUTO_INIT_SCHEMA", False),
        patch("psycopg2.connect", return_value=_Conn(_Cursor(revision="old"))),
        pytest.raises(RuntimeError, match="revision mismatch"),
    ):
        main_module._ensure_schema_ready()


def test_schema_verification_fails_when_required_table_missing():
    import api.main as main_module

    tables = set(main_module.REQUIRED_TABLES)
    tables.remove("documents")
    with (
        patch("api.main.AUTO_INIT_SCHEMA", False),
        patch("psycopg2.connect", return_value=_Conn(_Cursor(tables=tables))),
        pytest.raises(RuntimeError, match="Missing tables: documents"),
    ):
        main_module._ensure_schema_ready()


def test_auto_init_schema_is_rejected_in_production():
    import api.main as main_module

    with (
        patch("api.main.APP_ENV", "production"),
        patch("api.main.AUTO_INIT_SCHEMA", True),
        pytest.raises(RuntimeError, match="AUTO_INIT_SCHEMA"),
    ):
        main_module._ensure_schema_ready()


def test_auto_init_schema_runs_alembic_upgrade_in_development():
    import api.main as main_module

    with (
        patch("api.main.APP_ENV", "development"),
        patch("api.main.AUTO_INIT_SCHEMA", True),
        patch("api.main._run_alembic_upgrade") as upgrade,
        patch("psycopg2.connect", return_value=_Conn(_Cursor())),
    ):
        main_module._ensure_schema_ready()

    upgrade.assert_called_once()
