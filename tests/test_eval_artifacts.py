import json
from unittest.mock import patch

from eval.ragas_eval import run_eval
from scripts.plot_results import collect_latency_series, load_latency_results


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
        patch("retrieval.hybrid.HybridRetriever.retrieve", side_effect=retrieved_chunks),
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
