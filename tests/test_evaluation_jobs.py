import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from api.routers.evaluation import eval_history, eval_run_status, trigger_eval
from eval.auto_eval import (
    EvalJobAlreadyRunning,
    _claim_job,
    _complete_job,
    create_eval_job,
    get_eval_job,
    run_eval_job,
)


def _connection(cursor):
    cursor.__enter__.return_value = cursor
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.cursor.return_value = cursor
    return conn


def test_create_eval_job_inserts_queued_job_after_stale_recovery():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    conn = _connection(cursor)

    with (
        patch("eval.auto_eval.get_conn", return_value=conn),
        patch("eval.auto_eval.uuid.uuid4", return_value="run-1"),
        patch("eval.auto_eval._now_iso", return_value="2026-06-21T12:00:00+00:00"),
    ):
        run_id = create_eval_job("tenant-1")

    assert run_id == "run-1"
    assert "pg_advisory_xact_lock" in cursor.execute.call_args_list[0].args[0]
    assert "created_at < NOW()" in cursor.execute.call_args_list[1].args[0]
    insert_params = cursor.execute.call_args_list[3].args[1]
    config = json.loads(insert_params[3])
    assert config["status"] == "queued"
    assert config["retrieval_mode"] == "hybrid+rerank"
    conn.close.assert_called_once_with()


def test_create_eval_job_rejects_existing_active_job_without_insert():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("active-run",)
    conn = _connection(cursor)

    with (
        patch("eval.auto_eval.get_conn", return_value=conn),
        pytest.raises(EvalJobAlreadyRunning) as exc_info,
    ):
        create_eval_job("tenant-1")

    assert exc_info.value.run_id == "active-run"
    assert len(cursor.execute.call_args_list) == 3
    conn.close.assert_called_once_with()


def test_run_eval_job_persists_running_and_completed_states():
    scores = {"run_id": "generated", "n_queries": 2, "per_query": []}

    with (
        patch("eval.auto_eval._claim_job", return_value=True) as claim,
        patch("eval.auto_eval._tenant_slug", return_value="demo"),
        patch("eval.ragas_eval.run_eval", return_value=scores) as run_eval,
        patch("eval.auto_eval._complete_job") as complete,
    ):
        run_eval_job("job-1", "tenant-1")

    claim.assert_called_once_with("job-1", "tenant-1")
    assert run_eval.call_args.kwargs["tenant_slug"] == "demo"
    assert scores["run_id"] == "job-1"
    complete.assert_called_once_with("job-1", "tenant-1", scores)


def test_run_eval_job_skips_when_job_was_already_claimed():
    with (
        patch("eval.auto_eval._claim_job", return_value=False),
        patch("eval.ragas_eval.run_eval") as run_eval,
    ):
        run_eval_job("job-1", "tenant-1")

    run_eval.assert_not_called()


def test_run_eval_job_persists_failure_without_raising():
    with (
        patch("eval.auto_eval._claim_job", return_value=True),
        patch("eval.auto_eval._set_job_status") as set_status,
        patch("eval.auto_eval._tenant_slug", side_effect=RuntimeError("tenant lookup failed")),
    ):
        run_eval_job("job-1", "tenant-1")

    assert set_status.call_args.args[:3] == ("job-1", "tenant-1", "failed")
    assert set_status.call_args.kwargs["error"] == "tenant lookup failed"


def test_claim_job_marks_only_queued_job_as_running():
    cursor = MagicMock()
    cursor.fetchone.return_value = ("job-1",)
    conn = _connection(cursor)

    with (
        patch("eval.auto_eval.get_conn", return_value=conn),
        patch("eval.auto_eval._now_iso", return_value="2026-06-23T12:00:00+00:00"),
    ):
        claimed = _claim_job("job-1", "tenant-1")

    assert claimed is True
    query, params = cursor.execute.call_args.args
    config = json.loads(params[0])
    assert "COALESCE(config_json->>'status', 'queued') = 'queued'" in query
    assert "RETURNING id" in query
    assert config["status"] == "running"
    assert config["error"] is None
    assert params[1:] == ("job-1", "tenant-1")
    conn.close.assert_called_once_with()


def test_claim_job_returns_false_when_row_is_not_queued():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    conn = _connection(cursor)

    with patch("eval.auto_eval.get_conn", return_value=conn):
        assert _claim_job("job-1", "tenant-1") is False

    conn.close.assert_called_once_with()


def test_complete_job_persists_unified_metrics_and_tenant_scope():
    cursor = MagicMock()
    conn = _connection(cursor)
    scores = {
        "run_id": "job-1",
        "n_queries": 2,
        "per_query": [{"question": "Soru", "mrr": 1.0}],
        "faithfulness": 0.4,
        "answer_relevancy": 0.5,
        "context_precision": 0.6,
        "context_recall": 0.7,
        "mean_mrr": 0.8,
        "recall@5": 0.9,
        "total_latency_ms": 42.0,
    }

    with patch("eval.auto_eval.get_conn", return_value=conn):
        _complete_job("job-1", "tenant-1", scores)

    query, params = cursor.execute.call_args.args
    config = json.loads(params[0])
    metrics = json.loads(params[1])
    assert "WHERE id=%s AND tenant_id=%s" in query
    assert config["status"] == "completed"
    assert metrics["mean_mrr"] == 0.8
    assert metrics["recall@5"] == 0.9
    assert metrics["total_latency_ms"] == 42.0
    assert params[-2:] == ("job-1", "tenant-1")
    conn.close.assert_called_once_with()


def test_trigger_eval_returns_accepted_and_registers_background_task():
    tasks = BackgroundTasks()

    with (
        patch("eval.auto_eval.create_eval_job", return_value="job-1"),
        patch("eval.auto_eval.run_eval_job") as run_job,
    ):
        response = asyncio.run(trigger_eval(tasks, {"tenant_id": "tenant-1", "role": "admin"}))

    assert response == {"eval_run_id": "job-1", "status": "queued"}
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].func is run_job
    assert tasks.tasks[0].args == ("job-1", "tenant-1")


def test_trigger_eval_returns_conflict_for_active_job():
    tasks = BackgroundTasks()

    with (
        patch(
            "eval.auto_eval.create_eval_job",
            side_effect=EvalJobAlreadyRunning("active-run"),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        asyncio.run(trigger_eval(tasks, {"tenant_id": "tenant-1", "role": "admin"}))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["eval_run_id"] == "active-run"
    assert tasks.tasks == []


def test_eval_history_handles_decoded_jsonb_and_exposes_lifecycle():
    cursor = MagicMock()
    cursor.fetchall.return_value = [(
        "job-1",
        "api-auto-eval",
        {"status": "failed", "error": "model unavailable"},
        json.dumps({"faithfulness": 0.0}),
        [],
        0,
        0,
        "2026-06-21 12:00:00+00",
    )]
    conn = _connection(cursor)

    with patch("api.routers.evaluation.get_conn", return_value=conn):
        history = asyncio.run(eval_history({"tenant_id": "tenant-1", "role": "admin"}))

    assert history[0]["status"] == "failed"
    assert history[0]["error"] == "model unavailable"
    assert history[0]["metrics"] == {"faithfulness": 0.0}
    assert history[0]["per_query"] == []
    conn.close.assert_called_once_with()


def test_get_eval_job_returns_tenant_scoped_run_payload():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "job-1",
        "api-auto-eval",
        {"status": "running", "started_at": "2026-06-23T12:00:00+00:00"},
        {"recall@5": 0.75},
        [{"question": "Soru"}],
        1,
        0.5,
        "2026-06-23 12:00:00+00",
    )
    conn = _connection(cursor)

    with patch("eval.auto_eval.get_conn", return_value=conn):
        payload = get_eval_job("job-1", "tenant-1")

    query, params = cursor.execute.call_args.args
    assert "WHERE id=%s AND tenant_id=%s" in query
    assert params == ("job-1", "tenant-1")
    assert payload["id"] == "job-1"
    assert payload["status"] == "running"
    assert payload["metrics"] == {"recall@5": 0.75}
    assert payload["per_query"] == [{"question": "Soru"}]
    conn.close.assert_called_once_with()


def test_get_eval_job_returns_none_when_missing():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    conn = _connection(cursor)

    with patch("eval.auto_eval.get_conn", return_value=conn):
        assert get_eval_job("missing", "tenant-1") is None

    conn.close.assert_called_once_with()


def test_eval_run_status_returns_single_run():
    with patch("api.routers.evaluation.get_eval_job", return_value={"id": "job-1"}):
        payload = asyncio.run(eval_run_status("job-1", {"tenant_id": "tenant-1", "role": "admin"}))

    assert payload == {"id": "job-1"}


def test_eval_run_status_returns_404_for_missing_run():
    with (
        patch("api.routers.evaluation.get_eval_job", return_value=None),
        pytest.raises(HTTPException) as exc_info,
    ):
        asyncio.run(eval_run_status("missing", {"tenant_id": "tenant-1", "role": "admin"}))

    assert exc_info.value.status_code == 404
