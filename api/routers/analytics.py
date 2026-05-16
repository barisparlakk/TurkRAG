"""Query analytics endpoints — tenant-scoped stats and recent query log."""

import logging
import os
from fastapi import APIRouter, Depends
from api.auth import get_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


def _db():
    import psycopg2
    return psycopg2.connect(POSTGRES_URL)


@router.get("/stats")
async def get_stats(tenant_id: str = Depends(get_tenant_id)):
    """Return summary analytics for the current tenant."""
    conn = _db()
    try:
        with conn.cursor() as cur:
            # Overall totals
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

            # Top 5 most-asked questions (exact duplicates only — good enough for now)
            cur.execute(
                """SELECT query, COUNT(*) AS cnt
                   FROM query_logs WHERE tenant_id=%s
                   GROUP BY query ORDER BY cnt DESC LIMIT 5""",
                (tenant_id,),
            )
            top_queries = [{"query": r[0], "count": r[1]} for r in cur.fetchall()]

            # Top 5 most-cited documents
            cur.execute(
                """SELECT
                     elem->>'filename' AS filename,
                     COUNT(*)          AS citations
                   FROM messages,
                        jsonb_array_elements(citations) AS elem
                   WHERE session_id IN (
                       SELECT id FROM sessions WHERE tenant_id=%s
                   )
                   AND role = 'assistant'
                   AND jsonb_typeof(citations) = 'array'
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
    conn = _db()
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
