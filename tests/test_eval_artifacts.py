import json
from pathlib import Path
from unittest.mock import patch

import pytest

from eval.ragas_eval import run_eval, save_to_db
from scripts.audit_retrieval_artifacts import audit_retrieval_artifact
from scripts.plot_results import collect_latency_series, collect_recall_data, load_latency_results


def test_run_eval_persists_latency_metrics(tmp_path):
    queries_path = tmp_path / "queries.json"
    queries_path.write_text(json.dumps([
        {"question": "Soru 1", "ground_truth": "Yanıt 1", "relevant_doc": "doc-1.txt"},
        {"question": "Soru 2", "ground_truth": "Yanıt 2", "relevant_doc": "doc-2.txt"},
    ], ensure_ascii=False), encoding="utf-8")

    retrieved_chunks = [
        [{"text": "Yanıt 1 destek", "filename": "doc-1.txt", "chunk_index": 0}],
        [{"text": "Yanıt 2 destek", "filename": "doc-2.txt", "chunk_index": 1}],
    ]
    perf_counter_values = [
        0.00, 0.01, 0.01, 0.03, 0.05,
        0.10, 0.12, 0.12, 0.13, 0.14,
    ]

    with (
        patch("generation.llm.is_available", return_value=True),
        patch("generation.llm.generate", side_effect=["Yanıt 1", "Yanıt 2"]),
        patch("generation.prompt.build_prompt", return_value="prompt"),
        patch("retrieval.hybrid.HybridRetriever.retrieve", side_effect=retrieved_chunks) as retrieve,
        patch("eval.ragas_eval.compute_faithfulness", return_value=0.5),
        patch("eval.ragas_eval.compute_answer_relevancy", return_value=0.6),
        patch("eval.ragas_eval.compute_context_precision", return_value=0.7),
        patch("eval.ragas_eval.compute_context_recall", return_value=0.8),
        patch("eval.ragas_eval.time.perf_counter", side_effect=perf_counter_values),
    ):
        scores = run_eval("demo", str(queries_path), retrieval_mode="hybrid")

    assert scores["n_queries"] == 2
    assert round(scores["retrieval_latency_ms"], 3) == 15.0
    assert round(scores["generation_latency_ms"], 3) == 15.0
    assert round(scores["total_latency_ms"], 3) == 45.0
    assert [round(entry["total_latency_ms"], 1) for entry in scores["per_query"]] == [50.0, 40.0]
    assert scores["mean_mrr"] == 1.0
    assert scores["mean_ap"] == 1.0
    assert scores["recall@1"] == 1.0
    assert scores["recall@5"] == 1.0
    assert scores["ndcg@5"] == 1.0
    assert retrieve.call_count == 2


def test_run_eval_supports_multiple_relevant_documents(tmp_path):
    queries_path = tmp_path / "queries.json"
    queries_path.write_text(json.dumps([{
        "question": "Soru",
        "ground_truth": "Yanıt",
        "relevant_docs": ["policy.pdf", "leave.pdf"],
    }]), encoding="utf-8")
    chunks = [
        {"text": "Politika", "filename": "policy.pdf", "chunk_index": 0},
        {"text": "Tekrar", "filename": "policy.pdf", "chunk_index": 1},
        {"text": "İzin", "filename": "leave.pdf", "chunk_index": 0},
    ]

    with (
        patch("generation.llm.is_available", return_value=False),
        patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=chunks),
    ):
        scores = run_eval("demo", str(queries_path))

    assert scores["context_recall"] == 1.0
    assert scores["recall@1"] == 0.5
    assert scores["recall@3"] == 1.0
    assert scores["mean_ap"] < 1.0
    assert scores["per_query"][0]["relevant_docs"] == ["leave.pdf", "policy.pdf"]


def test_run_eval_keeps_retrieval_depth_for_metrics_and_slices_answer_context(tmp_path):
    queries_path = tmp_path / "queries.json"
    queries_path.write_text(json.dumps([{
        "question": "Soru",
        "relevant_doc": "doc-5.pdf",
    }]), encoding="utf-8")
    ranked_chunks = [
        {"text": f"İçerik {i}", "filename": f"doc-{i}.pdf", "chunk_index": 0}
        for i in range(1, 6)
    ]

    with (
        patch("generation.llm.is_available", return_value=False),
        patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=ranked_chunks) as retrieve,
    ):
        scores = run_eval("demo", str(queries_path), top_k=10, final_k=2)

    assert retrieve.call_args.kwargs["final_k"] == 5
    assert scores["context_recall"] == 0.0
    assert scores["recall@5"] == 1.0
    assert scores["per_query"][0]["context_docs"] == ["doc-1.pdf", "doc-2.pdf"]


def test_run_eval_rejects_depth_too_small_for_reported_metrics(tmp_path):
    queries_path = tmp_path / "queries.json"
    queries_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="top_k must be at least 5"):
        run_eval("demo", str(queries_path), top_k=3)


def test_save_to_db_persists_complete_metric_set_and_closes_resources():
    from unittest.mock import MagicMock

    cursor = MagicMock()
    cursor.fetchone.return_value = ("tenant-id",)
    conn = MagicMock()
    conn.cursor.return_value = cursor
    scores = {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "tenant_slug": "demo",
        "run_label": "unified",
        "retrieval_mode": "hybrid",
        "top_k": 20,
        "final_k": 5,
        "n_queries": 1,
        "per_query": [{"question": "Soru", "mrr": 1.0}],
        "faithfulness": 0.5,
        "answer_relevancy": 0.6,
        "context_precision": 0.7,
        "context_recall": 0.8,
        "mean_mrr": 1.0,
        "mean_ap": 0.9,
        "recall@1": 1.0,
        "recall@3": 1.0,
        "recall@5": 1.0,
        "ndcg@1": 1.0,
        "ndcg@3": 1.0,
        "ndcg@5": 1.0,
        "retrieval_latency_ms": 10.0,
        "generation_latency_ms": 20.0,
        "total_latency_ms": 30.0,
    }

    with patch("psycopg2.connect", return_value=conn):
        save_to_db(scores)

    insert_params = cursor.execute.call_args_list[1].args[1]
    persisted_metrics = json.loads(insert_params[4])
    persisted_queries = json.loads(insert_params[5])
    assert persisted_metrics["mean_mrr"] == 1.0
    assert persisted_metrics["recall@3"] == 1.0
    assert persisted_metrics["ndcg@5"] == 1.0
    assert persisted_metrics["total_latency_ms"] == 30.0
    assert persisted_queries == scores["per_query"]
    cursor.close.assert_called_once_with()
    conn.close.assert_called_once_with()


def test_plot_results_loads_matching_mode_json_for_latency(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    csv_path = results_dir / "experiment_20260611_170000.csv"
    csv_path.write_text("retrieval_mode\nhybrid\n", encoding="utf-8")

    hybrid_json = results_dir / "20260611_170000_hybrid.json"
    hybrid_json.write_text(json.dumps({
        "retrieval_mode": "hybrid",
        "per_query": [{"total_latency_ms": 12.5}, {"total_latency_ms": 18.0}],
    }), encoding="utf-8")

    dense_json = results_dir / "20260611_170000_dense.json"
    dense_json.write_text(json.dumps({
        "retrieval_mode": "dense",
        "per_query": [{"total_latency_ms": 9.0}],
    }), encoding="utf-8")

    loaded = load_latency_results(str(csv_path))
    latency_series = collect_latency_series(loaded)

    assert {entry["retrieval_mode"] for entry in loaded} == {"hybrid", "dense"}
    assert latency_series == {"dense": [9.0], "hybrid": [12.5, 18.0]}


def test_collect_latency_series_uses_csv_aggregate_when_per_query_missing():
    latency_series = collect_latency_series([
        {"retrieval_mode": "sparse", "total_latency_ms": "31.5"},
        {"retrieval_mode": "dense", "total_latency_ms": 22.0, "per_query": []},
        {"retrieval_mode": "hybrid", "per_query": [{"total_latency_ms": 12.0}]},
        {"retrieval_mode": "broken", "total_latency_ms": ""},
    ])

    assert latency_series == {
        "dense": [22.0],
        "hybrid": [12.0],
        "sparse": [31.5],
    }


def test_collect_recall_data_accepts_unified_flat_metrics():
    data = collect_recall_data([
        {"retrieval_mode": "hybrid", "recall@1": "0.4", "recall@3": "0.8", "recall@5": "1.0"},
        {"retrieval_mode": "dense", "error": "failed"},
    ])

    assert data == [{
        "retrieval_mode": "hybrid",
        "recall_at_k": {"1": "0.4", "3": "0.8", "5": "1.0"},
    }]


def test_committed_eval_artifacts_do_not_contain_scratchpad_text():
    root = Path(__file__).resolve().parent.parent
    artifact_paths = [
        root / "eval" / "eval_set_generated.csv",
        root / "results" / "retrieval_metrics_47q.json",
        root / "results" / "20260522_132834_sparse.json",
        root / "results" / "20260522_132834_dense.json",
        root / "results" / "20260522_132834_hybrid.json",
        root / "results" / "20260522_132834_hybrid_rerank.json",
    ]

    for path in artifact_paths:
        contents = path.read_text(encoding="utf-8")
        lowered = contents.lower()
        assert "<think>" not in contents, f"scratchpad tag found in {path.name}"
        assert "okay, let's see." not in lowered, f"reasoning preamble found in {path.name}"


def test_audit_retrieval_artifact_flags_out_of_range_metrics_and_blank_questions(tmp_path):
    artifact_path = tmp_path / "retrieval_metrics_2q.json"
    artifact_path.write_text(json.dumps([{
        "aggregate": {
            "n_queries": 3,
            "mean_mrr": 1.2,
            "mean_ap": 0.5,
            "recall_at_k": {"1": 1.1},
            "precision_at_k": {"1": 0.5},
            "ndcg_at_k": {"1": 0.5},
        },
        "per_query": [
            {"question": "", "mrr": 0.5, "ap": 0.5, "recall@1": 0.0, "precision@1": 0.0, "ndcg@1": 0.0},
            {"question": "Soru", "mrr": 0.5, "ap": 0.5, "recall@1": 1.5, "precision@1": 0.5, "ndcg@1": 0.5},
        ],
    }]), encoding="utf-8")

    issues = audit_retrieval_artifact(artifact_path)

    assert any("n_queries=3" in issue for issue in issues)
    assert any("filename implies 2 queries" in issue for issue in issues)
    assert any("mean_mrr" in issue for issue in issues)
    assert any("recall_at_k.1" in issue for issue in issues)
    assert any("blank per_query question values" in issue for issue in issues)
    assert any("per_query row #2" in issue and "recall@1" in issue for issue in issues)
