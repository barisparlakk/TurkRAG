"""Evaluation API endpoints."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.auth import get_tenant_id
from api.db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eval", tags=["evaluation"])


@router.post("/run")
async def trigger_eval(background_tasks: BackgroundTasks, tenant_id: str = Depends(get_tenant_id)):
    """Trigger an evaluation run. Returns immediately with status."""
    from eval.auto_eval import run_evaluation, save_eval_result

    try:
        result = run_evaluation(tenant_id)
        run_id = save_eval_result(result)
        return {
            "eval_run_id": run_id,
            "status": "completed",
            "metrics": {
                "faithfulness": result.faithfulness,
                "answer_relevancy": result.answer_relevancy,
                "context_precision": result.context_precision,
                "avg_score": result.avg_score,
            },
            "num_queries": result.num_queries,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Evaluation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")


@router.get("/history")
async def eval_history(tenant_id: str = Depends(get_tenant_id)):
    """Return past evaluation runs for trend tracking."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, metrics_json, num_queries, avg_score, created_at
                   FROM eval_runs WHERE tenant_id=%s
                   ORDER BY created_at DESC LIMIT 50""",
                (tenant_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    import json
    return [
        {
            "id": str(r[0]),
            "metrics": json.loads(r[1]) if r[1] else {},
            "num_queries": r[2],
            "avg_score": float(r[3]) if r[3] else 0.0,
            "created_at": str(r[4]),
        }
        for r in rows
    ]
