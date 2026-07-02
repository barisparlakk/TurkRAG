"""Dashboard summary ACL regressions."""

import asyncio
from unittest.mock import patch


class _DashboardCursor:
    def __init__(self):
        self.queries = []
        self.query = ""
        self.params = None

    def execute(self, query, params=None):
        self.query = query
        self.params = params
        self.queries.append((query, params))

    def fetchone(self):
        query = self.query
        if "COUNT(*) FILTER (WHERE status='ready')" in query and "FROM documents" in query:
            if "AND false" in query:
                return (0, 0, 0, 0)
            return (1, 1, 0, 0) if "id = ANY" in query else (2, 2, 0, 0)
        if "COUNT(*) FROM collections" in query:
            return (1,)
        if "FROM query_logs" in query:
            return (3, 2, 120)
        if "FROM eval_runs" in query:
            return (0.91, "nightly", "completed", "2026-07-02T08:00:00")
        return None

    def fetchall(self):
        query = self.query
        params = self.params or ()
        if "FROM documents" in query and "ORDER BY created_at DESC" in query:
            if "AND false" in query:
                return []
            if "id = ANY" in query and list(params[-1]) == ["doc-visible"]:
                return [("doc-visible", "visible.pdf", "ready", "2026-07-02T08:04:00")]
            return [
                ("doc-private", "private.pdf", "ready", "2026-07-02T08:05:00"),
                ("doc-visible", "visible.pdf", "ready", "2026-07-02T08:04:00"),
            ]
        if "FROM ingestion_jobs j" in query:
            if "AND false" in query:
                return []
            if "d.id = ANY" in query and list(params[-1]) == ["doc-visible"]:
                return [
                    (
                        "job-visible",
                        "visible.pdf",
                        "completed",
                        1,
                        3,
                        "2026-07-02T08:03:00",
                        "2026-07-02T08:03:01",
                        "2026-07-02T08:03:10",
                        "2026-07-02T08:03:05",
                    )
                ]
            return [
                (
                    "job-private",
                    "private.pdf",
                    "completed",
                    1,
                    3,
                    "2026-07-02T08:06:00",
                    None,
                    None,
                    None,
                ),
                (
                    "job-visible",
                    "visible.pdf",
                    "completed",
                    1,
                    3,
                    "2026-07-02T08:03:00",
                    None,
                    None,
                    None,
                ),
            ]
        if "FROM collections c" in query:
            if "AND false" in query:
                return [("collection-1", "Policies", "#4f8cff", 0, 0)]
            if "d.id = ANY" in query and list(params[0]) == ["doc-visible"]:
                return [("collection-1", "Policies", "#4f8cff", 1, 1)]
            return [("collection-1", "Policies", "#4f8cff", 2, 2)]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DashboardConn:
    def __init__(self):
        self.cursor_obj = _DashboardCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def test_dashboard_summary_filters_member_activity_and_collection_counts():
    from api.routers import dashboard

    conn = _DashboardConn()
    user = {"id": "member-1", "tenant_id": "tenant-1", "role": "member"}

    with (
        patch("api.routers.dashboard.get_conn", return_value=conn),
        patch("api.routers.dashboard.get_accessible_document_ids", return_value=["doc-visible"]),
    ):
        result = asyncio.run(dashboard.dashboard_summary(user))

    assert result["documents"]["total"] == 1
    assert result["collections"]["top"][0]["document_count"] == 1
    assert [item["id"] for item in result["recent_activity"]] == ["doc-visible", "job-visible"]
    assert any("FROM ingestion_jobs j" in query and "d.id = ANY" in query for query, _ in conn.cursor_obj.queries)
    assert any("FROM collections c" in query and "d.id = ANY" in query for query, _ in conn.cursor_obj.queries)


def test_dashboard_summary_returns_empty_member_activity_without_accessible_docs():
    from api.routers import dashboard

    conn = _DashboardConn()
    user = {"id": "member-1", "tenant_id": "tenant-1", "role": "member"}

    with (
        patch("api.routers.dashboard.get_conn", return_value=conn),
        patch("api.routers.dashboard.get_accessible_document_ids", return_value=[]),
    ):
        result = asyncio.run(dashboard.dashboard_summary(user))

    assert result["documents"]["total"] == 0
    assert result["collections"]["top"][0]["document_count"] == 0
    assert result["recent_activity"] == []
    assert any("FROM ingestion_jobs j" in query and "AND false" in query for query, _ in conn.cursor_obj.queries)
