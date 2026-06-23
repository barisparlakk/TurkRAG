"""Evaluation API endpoints."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from api.auth import require_admin
from api.db import get_conn
from eval.auto_eval import _eval_run_payload, get_eval_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_eval(background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    """Queue an evaluation job and return without waiting for model execution."""
    from eval.auto_eval import EvalJobAlreadyRunning, create_eval_job, run_eval_job

    try:
        tenant_id = user["tenant_id"]
        run_id = create_eval_job(tenant_id)
        background_tasks.add_task(run_eval_job, run_id, tenant_id)
        return {"eval_run_id": run_id, "status": "queued"}
    except EvalJobAlreadyRunning as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "An evaluation job is already active", "eval_run_id": exc.run_id},
        ) from exc
    except Exception as exc:
        logger.exception("Could not queue evaluation: %s", exc)
        raise HTTPException(status_code=500, detail="Could not queue evaluation") from exc


@router.get("/history")
async def eval_history(user: dict = Depends(require_admin)):
    """Return past evaluation runs for trend tracking."""
    tenant_id = user["tenant_id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, run_label, config_json, metrics_json, per_query_json,
                          num_queries, avg_score, created_at
                   FROM eval_runs WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT 50""",
                (tenant_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [_eval_run_payload(row) for row in rows]


@router.get("/runs/{run_id}")
async def eval_run_status(run_id: str, user: dict = Depends(require_admin)):
    """Return one tenant-scoped evaluation run for focused polling."""
    eval_run = get_eval_job(run_id, user["tenant_id"])
    if eval_run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return eval_run
