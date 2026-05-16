"""Query analytics endpoints — tenant-scoped stats and recent query log."""

import logging

from fastapi import APIRouter, Depends

from api.auth import get_tenant_id
from api.db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/stats")
async def get_stats(tenant_id: str = Depends(get_tenant_id)):
    """Return summary analytics for the current tenant."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT
                     COUNT(*)                          AS total_queries,
                     ROUND(AVG(query_time_ms))         AS avg_query_time_ms,
                     COUNT(*) FILTER (
                         WHERE created_at >= NOW() - INTERVAL '24 hours'
                     )                                 AS queries_today
                   FROM query_logs WHERE tenant_id=%s""",
                (tenant_id,),
            )
            row = cur.fetchone()
            total_queries, avg_query_time_ms, queries_today = row or (0, 0, 0)

            cur.execute(
                """SELECT query, COUNT(*) AS cnt
                   FROM query_logs WHERE tenant_id=%s
                   GROUP BY query ORDER BY cnt DESC LIMIT 5""",
                (tenant_id,),
            )
            top_queries = [{"query": r[0], "count": r[1]} for r in cur.fetchall()]

            cur.execute(
                """SELECT
                     elem->>'filename' AS filename,
                     COUNT(*)          AS citations
                   FROM messages
                   JOIN sessions ON sessions.id = messages.session_id
                        AND sessions.tenant_id = %s
                   CROSS JOIN LATERAL jsonb_array_elements(messages.citations) AS elem
                   WHERE messages.role = 'assistant'
                     AND jsonb_typeof(messages.citations) = 'array'
                   GROUP BY filename
                   ORDER BY citations DESC LIMIT 5""",
                (tenant_id,),
            )
            top_docs = [{"filename": r[0], "citations": r[1]} for r in cur.fetchall()]

    finally:
        conn.close()

    return {
        "total_queries": total_queries or 0,
        "avg_query_time_ms": int(avg_query_time_ms or 0),
        "queries_today": queries_today or 0,
        "top_queries": top_queries,
        "top_documents": top_docs,
    }


@router.get("/recent")
async def get_recent(limit: int = 20, tenant_id: str = Depends(get_tenant_id)):
    """Return the most recent query log entries for the current tenant."""
    limit = min(max(limit, 1), 100)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, query, answer_length, num_citations, query_time_ms, created_at
                   FROM query_logs
                   WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": str(r[0]),
            "query": r[1],
            "answer_length": r[2],
            "num_citations": r[3],
            "query_time_ms": r[4],
            "created_at": str(r[5]),
        }
        for r in rows
    ]
