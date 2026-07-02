"""Dashboard summary endpoints."""

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.db import get_conn
from api.rbac import get_accessible_document_ids

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fmt_date(value):
    return str(value) if value else None


@router.get("/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    """Return a compact tenant dashboard summary for the frontend console."""
    tenant_id = user["tenant_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            is_admin = user.get("role") == "admin"
            accessible_ids = None
            doc_filter = ""
            params = [tenant_id]
            doc_filter_for_alias = ""
            collection_params = [tenant_id]
            job_filter = ""
            job_params = [tenant_id]
            if user.get("role") != "admin":
                accessible_ids = get_accessible_document_ids(user["id"], tenant_id, conn)
                if not accessible_ids:
                    doc_filter = "AND false"
                    doc_filter_for_alias = "AND false"
                    job_filter = "AND false"
                else:
                    doc_filter = "AND id = ANY(%s)"
                    params.append(accessible_ids)
                    doc_filter_for_alias = "AND d.id = ANY(%s)"
                    collection_params = [accessible_ids, tenant_id]
                    job_filter = "AND d.id = ANY(%s)"
                    job_params.append(accessible_ids)

            cur.execute(
                f"""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE status='ready'),
                       COUNT(*) FILTER (WHERE status IN ('processing', 'pending')),
                       COUNT(*) FILTER (WHERE status IN ('failed', 'error'))
                FROM documents
                WHERE tenant_id=%s {doc_filter}
                """,
                tuple(params),
            )
            doc_total, doc_ready, doc_processing, doc_failed = cur.fetchone() or (0, 0, 0, 0)

            cur.execute("SELECT COUNT(*) FROM collections WHERE tenant_id=%s", (tenant_id,))
            collection_total = cur.fetchone()[0]

            owner_filter = ""
            query_params = [tenant_id]
            if user.get("role") != "admin":
                owner_filter = "AND s.user_id=%s"
                query_params.append(user["id"])
            cur.execute(
                f"""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE q.created_at >= NOW() - INTERVAL '7 days'),
                       ROUND(AVG(q.query_time_ms))
                FROM query_logs q
                LEFT JOIN sessions s ON s.id = q.session_id
                WHERE q.tenant_id=%s {owner_filter}
                """,
                tuple(query_params),
            )
            query_total, query_week, avg_query_time_ms = cur.fetchone() or (0, 0, 0)

            cur.execute(
                """SELECT avg_score, run_label,
                          COALESCE(config_json->>'status', 'completed') AS status,
                          created_at
                   FROM eval_runs
                   WHERE tenant_id=%s
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (tenant_id,),
            )
            eval_row = cur.fetchone()

            cur.execute(
                f"""SELECT id, filename, status, created_at
                   FROM documents
                   WHERE tenant_id=%s {doc_filter}
                   ORDER BY created_at DESC
                   LIMIT 4""",
                tuple(params),
            )
            recent_docs = cur.fetchall()

            cur.execute(
                f"""SELECT j.id, j.filename, j.status, j.attempts, j.max_attempts, j.created_at,
                          j.started_at, j.completed_at, j.last_heartbeat_at
                   FROM ingestion_jobs j
                   LEFT JOIN documents d ON d.id = j.document_id AND d.tenant_id = j.tenant_id
                   WHERE j.tenant_id=%s {job_filter}
                   ORDER BY j.created_at DESC
                   LIMIT 4""",
                tuple(job_params),
            )
            recent_jobs = cur.fetchall()

            if is_admin:
                cur.execute(
                    """SELECT c.id, c.name, c.color,
                              COUNT(d.id) AS document_count,
                              COUNT(d.id) FILTER (WHERE d.status='ready') AS ready_count
                       FROM collections c
                       LEFT JOIN documents d ON d.collection_id=c.id AND d.tenant_id=c.tenant_id
                       WHERE c.tenant_id=%s
                       GROUP BY c.id
                       ORDER BY document_count DESC, c.created_at DESC
                       LIMIT 4""",
                    (tenant_id,),
                )
            else:
                cur.execute(
                    f"""SELECT c.id, c.name, c.color,
                              COUNT(d.id) AS document_count,
                              COUNT(d.id) FILTER (WHERE d.status='ready') AS ready_count
                       FROM collections c
                       LEFT JOIN documents d
                         ON d.collection_id=c.id
                        AND d.tenant_id=c.tenant_id
                        {doc_filter_for_alias}
                       WHERE c.tenant_id=%s
                       GROUP BY c.id
                       ORDER BY document_count DESC, c.created_at DESC
                       LIMIT 4""",
                    tuple(collection_params),
                )
            collections = cur.fetchall()
    finally:
        conn.close()

    accuracy = None
    if eval_row and eval_row[0] is not None:
        accuracy = round(float(eval_row[0]) * 100, 1)

    activity = [
        {
            "type": "document",
            "id": str(row[0]),
            "title": row[1],
            "status": row[2],
            "created_at": _fmt_date(row[3]),
        }
        for row in recent_docs
    ] + [
        {
            "type": "job",
            "id": str(row[0]),
            "title": row[1],
            "status": row[2],
            "attempts": int(row[3] or 0),
            "max_attempts": int(row[4] or 0),
            "created_at": _fmt_date(row[5]),
            "started_at": _fmt_date(row[6]),
            "completed_at": _fmt_date(row[7]),
            "last_heartbeat_at": _fmt_date(row[8]),
        }
        for row in recent_jobs
    ]

    return {
        "documents": {
            "total": int(doc_total or 0),
            "ready": int(doc_ready or 0),
            "processing": int(doc_processing or 0),
            "failed": int(doc_failed or 0),
        },
        "collections": {
            "total": int(collection_total or 0),
            "top": [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "color": row[2],
                    "document_count": int(row[3] or 0),
                    "ready_count": int(row[4] or 0),
                }
                for row in collections
            ],
        },
        "queries": {
            "total": int(query_total or 0),
            "last_7_days": int(query_week or 0),
            "avg_query_time_ms": int(avg_query_time_ms or 0),
        },
        "accuracy": {
            "average": accuracy,
            "status": eval_row[2] if eval_row else None,
            "label": eval_row[1] if eval_row else None,
            "created_at": _fmt_date(eval_row[3]) if eval_row else None,
        },
        "recent_activity": sorted(activity, key=lambda item: item.get("created_at") or "", reverse=True)[:8],
    }
