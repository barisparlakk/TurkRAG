"""Persisted background-job orchestration for API-triggered evaluations."""

import json
import logging
import os
import uuid
from datetime import UTC, datetime

from api.config import positive_int_env
from api.db import get_conn

logger = logging.getLogger(__name__)

EVAL_QUERIES_PATH = os.getenv("EVAL_QUERIES_PATH", "eval/test_queries.json")
EVAL_RETRIEVAL_MODE = os.getenv("EVAL_RETRIEVAL_MODE", "hybrid+rerank")
EVAL_TOP_K = positive_int_env("EVAL_TOP_K", 20)
EVAL_FINAL_K = positive_int_env("EVAL_FINAL_K", 5)
EVAL_STALE_JOB_TIMEOUT_SECONDS = positive_int_env("EVAL_STALE_JOB_TIMEOUT_SECONDS", 3600)


class EvalJobAlreadyRunning(Exception):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Evaluation job already active: {run_id}")


def _json_value(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if isinstance(value, type(default)) else default


def _eval_run_payload(row) -> dict:
    config = _json_value(row[2], {})
    return {
        "id": str(row[0]),
        "run_label": row[1],
        "status": config.get("status", "completed"),
        "error": config.get("error"),
        "config": config,
        "metrics": _json_value(row[3], {}),
        "per_query": _json_value(row[4], []),
        "num_queries": row[5],
        "avg_score": float(row[6]) if row[6] else 0.0,
        "created_at": str(row[7]),
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _base_config(status: str) -> dict:
    return {
        "source": "api",
        "status": status,
        "retrieval_mode": EVAL_RETRIEVAL_MODE,
        "top_k": EVAL_TOP_K,
        "final_k": EVAL_FINAL_K,
        "queries_path": EVAL_QUERIES_PATH,
    }


def create_eval_job(tenant_id: str) -> str:
    """Atomically create one queued evaluation job per tenant."""
    run_id = str(uuid.uuid4())
    active_run_id = None
    stale_patch = json.dumps({
        "status": "failed",
        "error": "Evaluation worker stopped before completion",
        "failed_at": _now_iso(),
    })

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            # Serialize the stale-check/insert pair without requiring a schema change.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"eval:{tenant_id}",))
            cur.execute(
                """UPDATE eval_runs
                   SET config_json = COALESCE(config_json, '{}'::jsonb) || %s::jsonb
                   WHERE tenant_id=%s
                     AND config_json->>'status' IN ('queued', 'running')
                     AND created_at < NOW() - (%s * INTERVAL '1 second')""",
                (stale_patch, tenant_id, EVAL_STALE_JOB_TIMEOUT_SECONDS),
            )
            cur.execute(
                """SELECT id FROM eval_runs
                   WHERE tenant_id=%s
                     AND config_json->>'status' IN ('queued', 'running')
                   ORDER BY created_at DESC LIMIT 1""",
                (tenant_id,),
            )
            row = cur.fetchone()
            if row:
                active_run_id = str(row[0])
            else:
                cur.execute(
                    """INSERT INTO eval_runs
                          (id, tenant_id, run_label, config_json, metrics_json, per_query_json,
                           num_queries, avg_score)
                       VALUES (%s, %s, %s, %s, %s, %s, 0, 0)""",
                    (
                        run_id,
                        tenant_id,
                        "api-auto-eval",
                        json.dumps({**_base_config("queued"), "queued_at": _now_iso()}),
                        json.dumps({}),
                        json.dumps([]),
                    ),
                )
    finally:
        conn.close()

    if active_run_id is not None:
        raise EvalJobAlreadyRunning(active_run_id)
    return run_id


def _tenant_slug(tenant_id: str) -> str:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"Tenant not found: {tenant_id}")
    return row[0]


def _set_job_status(run_id: str, tenant_id: str, status: str, **details) -> None:
    patch = {"status": status, **details}
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE eval_runs
                   SET config_json = COALESCE(config_json, '{}'::jsonb) || %s::jsonb
                   WHERE id=%s AND tenant_id=%s""",
                (json.dumps(patch), run_id, tenant_id),
            )
    finally:
        conn.close()


def _claim_job(run_id: str, tenant_id: str) -> bool:
    """Move a queued job to running exactly once."""
    patch = {"status": "running", "started_at": _now_iso(), "error": None}
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE eval_runs
                   SET config_json = COALESCE(config_json, '{}'::jsonb) || %s::jsonb
                   WHERE id=%s
                     AND tenant_id=%s
                     AND COALESCE(config_json->>'status', 'queued') = 'queued'
                   RETURNING id""",
                (json.dumps(patch), run_id, tenant_id),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def get_eval_job(run_id: str, tenant_id: str) -> dict | None:
    """Return one tenant-scoped evaluation run for status polling."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, run_label, config_json, metrics_json, per_query_json,
                          num_queries, avg_score, created_at
                   FROM eval_runs
                   WHERE id=%s AND tenant_id=%s""",
                (run_id, tenant_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return _eval_run_payload(row) if row else None


def _complete_job(run_id: str, tenant_id: str, scores: dict) -> None:
    from eval.ragas_eval import LATENCY_FIELDS, METRICS, RETRIEVAL_METRICS

    metric_fields = METRICS + RETRIEVAL_METRICS + LATENCY_FIELDS
    metrics = {field: scores.get(field, 0.0) for field in metric_fields}
    avg_score = sum(scores.get(field, 0.0) for field in METRICS) / len(METRICS)
    config_patch = {
        "status": "completed",
        "completed_at": _now_iso(),
        "run_id": scores["run_id"],
    }

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE eval_runs
                   SET config_json = COALESCE(config_json, '{}'::jsonb) || %s::jsonb,
                       metrics_json=%s, per_query_json=%s, num_queries=%s, avg_score=%s
                   WHERE id=%s AND tenant_id=%s""",
                (
                    json.dumps(config_patch),
                    json.dumps(metrics),
                    json.dumps(scores.get("per_query", [])),
                    scores["n_queries"],
                    avg_score,
                    run_id,
                    tenant_id,
                ),
            )
    finally:
        conn.close()


def run_eval_job(run_id: str, tenant_id: str) -> None:
    """Execute a queued job and persist completed or failed state."""
    from eval.ragas_eval import run_eval

    try:
        if not _claim_job(run_id, tenant_id):
            logger.warning("Evaluation job %s was not queued; skipping execution", run_id)
            return
        scores = run_eval(
            tenant_slug=_tenant_slug(tenant_id),
            queries_path=EVAL_QUERIES_PATH,
            retrieval_mode=EVAL_RETRIEVAL_MODE,
            top_k=EVAL_TOP_K,
            final_k=EVAL_FINAL_K,
            run_label="api-auto-eval",
        )
        scores["run_id"] = run_id
        _complete_job(run_id, tenant_id, scores)
        logger.info("Evaluation job %s completed for tenant %s", run_id, tenant_id)
    except Exception as exc:
        logger.exception("Evaluation job %s failed: %s", run_id, exc)
        try:
            _set_job_status(
                run_id,
                tenant_id,
                "failed",
                failed_at=_now_iso(),
                error=str(exc)[:1000],
            )
        except Exception:
            logger.exception("Could not persist failed state for evaluation job %s", run_id)
