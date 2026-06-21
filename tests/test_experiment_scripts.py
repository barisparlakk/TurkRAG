"""Lightweight CLI coverage for experiment scripts."""

import json
import os


def test_run_experiments_uses_single_unified_eval_pass(tmp_path, monkeypatch):
    import eval.ragas_eval as ragas
    import eval.retrieval_metrics as retrieval_metrics
    import scripts.run_experiments as experiments

    calls = []
    saved_to_db = []

    def fake_run_eval(**kwargs):
        calls.append(kwargs)
        return {
            "retrieval_mode": kwargs["retrieval_mode"],
            "run_label": kwargs["run_label"],
            "faithfulness": 0.5,
            "answer_relevancy": 0.6,
            "context_precision": 0.7,
            "context_recall": 0.8,
            "mean_mrr": 0.9,
            "mean_ap": 0.85,
            "recall@1": 0.4,
            "recall@3": 0.8,
            "recall@5": 1.0,
            "ndcg@1": 0.4,
            "ndcg@3": 0.7,
            "ndcg@5": 0.9,
            "retrieval_latency_ms": 10.0,
            "generation_latency_ms": 20.0,
            "total_latency_ms": 30.0,
            "n_queries": 2,
            "top_k": kwargs["top_k"],
            "final_k": kwargs["final_k"],
            "evaluated_at": "2026-06-21T00:00:00",
            "per_query": [{"question": "Soru", "recall@5": 1.0}],
        }

    monkeypatch.setattr(ragas, "run_eval", fake_run_eval)
    monkeypatch.setattr(ragas, "save_to_db", lambda scores: saved_to_db.append(scores))
    monkeypatch.setattr(
        retrieval_metrics,
        "evaluate_retrieval",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("duplicate retrieval pass")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_experiments.py",
            "--tenant",
            "demo",
            "--modes",
            "hybrid",
            "--save-db",
            "--output-dir",
            str(tmp_path),
        ],
    )

    experiments.main()

    assert len(calls) == 1
    assert saved_to_db[0]["mean_mrr"] == 0.9
    csv_path = next(tmp_path.glob("experiment_*.csv"))
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "recall@1" in csv_text
    assert "ndcg@5" in csv_text
    mode_result = next(path for path in tmp_path.glob("*_hybrid.json"))
    assert json.loads(mode_result.read_text(encoding="utf-8"))["per_query"]


def test_chunking_experiments_main_writes_results_and_cleans_up(tmp_path, monkeypatch):
    import scripts.chunking_experiments as chunking

    output_path = tmp_path / "chunking.json"
    indexed = []
    cleaned = []

    monkeypatch.setattr(chunking, "load_raw_texts_from_bm25", lambda tenant: [("doc text", {"doc_id": "1"})])
    monkeypatch.setattr(
        chunking,
        "rechunk_and_index",
        lambda docs, strategy, temp_tenant: indexed.append((strategy, temp_tenant, len(docs))),
    )
    monkeypatch.setattr(
        chunking,
        "evaluate_strategy",
        lambda temp_tenant, queries_path, mode, ks: {
            "mean_mrr": 0.5,
            "recall_at_k": {str(k): round(k / 10, 3) for k in ks},
            "tenant_slug": temp_tenant,
        },
    )
    monkeypatch.setattr(chunking, "cleanup_temp_tenant", lambda temp_tenant: cleaned.append(temp_tenant))
    monkeypatch.setattr(
        "sys.argv",
        [
            "chunking_experiments.py",
            "--tenant",
            "demo",
            "--strategies",
            "turkish",
            "paragraph",
            "--ks",
            "1",
            "5",
            "--output",
            str(output_path),
        ],
    )

    chunking.main()

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert [entry["chunker_strategy"] for entry in saved] == ["turkish", "paragraph"]
    assert saved[0]["chunker_config"] == chunking.STRATEGY_CONFIGS["turkish"]
    assert indexed == [
        ("turkish", "demo__chunk_exp_turkish", 1),
        ("paragraph", "demo__chunk_exp_paragraph", 1),
    ]
    assert cleaned == ["demo__chunk_exp_turkish", "demo__chunk_exp_paragraph"]


def test_embedder_experiments_main_uses_discovered_models(tmp_path, monkeypatch):
    import ingestion.embedder as embedder
    import scripts.embedder_experiments as experiments

    output_path = tmp_path / "embedder.json"
    built = []
    cleaned = []

    monkeypatch.setattr(embedder, "list_available_models", lambda: ["model-a", "model-b"])
    monkeypatch.setattr(experiments, "load_chunks_from_bm25", lambda tenant: (["chunk"], [{"doc_id": "1"}]))
    monkeypatch.setattr(
        experiments,
        "build_temp_qdrant",
        lambda texts, payloads, model_path, temp_tenant: built.append((model_path, temp_tenant, len(texts))),
    )
    monkeypatch.setattr(
        experiments,
        "evaluate_embedder",
        lambda temp_tenant, queries_path, model_path, ks: {
            "mean_mrr": 0.4,
            "recall_at_k": {str(k): 1.0 for k in ks},
            "tenant_slug": temp_tenant,
        },
    )
    monkeypatch.setattr(experiments, "cleanup_temp_qdrant", lambda temp_tenant: cleaned.append(temp_tenant))
    monkeypatch.setattr(
        "sys.argv",
        [
            "embedder_experiments.py",
            "--tenant",
            "demo",
            "--ks",
            "1",
            "3",
            "--output",
            str(output_path),
        ],
    )

    experiments.main()

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert [entry["embedder"] for entry in saved] == ["model-a", "model-b"]
    assert saved[0]["model_path"] == "models/model-a"
    assert built == [
        ("models/model-a", "demo__emb_exp_model-a", 1),
        ("models/model-b", "demo__emb_exp_model-b", 1),
    ]
    assert cleaned == ["demo__emb_exp_model-a", "demo__emb_exp_model-b"]


def test_evaluate_embedder_restores_environment(monkeypatch):
    import scripts.embedder_experiments as experiments

    captured = []

    def fake_eval(**kwargs):
        captured.append(os.environ.get("EMBEDDING_MODEL"))
        return {"aggregate": {"mean_mrr": 0.25, "recall_at_k": {"1": 0.5}}}

    monkeypatch.setenv("EMBEDDING_MODEL", "models/original")
    monkeypatch.setattr("eval.retrieval_metrics.evaluate_retrieval", fake_eval)

    aggregate = experiments.evaluate_embedder("demo__emb_exp_model-a", "queries.json", "models/model-a", [1])

    assert aggregate["mean_mrr"] == 0.25
    assert captured == ["models/model-a"]
    assert os.environ["EMBEDDING_MODEL"] == "models/original"


def test_hyperparameter_sweep_filters_invalid_combos_and_sorts_results(tmp_path, monkeypatch):
    import scripts.hyperparameter_sweep as sweep

    output_path = tmp_path / "sweep.json"
    indexed = []
    cleaned = []
    evaluated = []

    monkeypatch.setattr(
        sweep,
        "_rechunk_and_index",
        lambda tenant, temp_slug, chunk_size, overlap: indexed.append((tenant, temp_slug, chunk_size, overlap)),
    )
    monkeypatch.setattr(sweep, "_cleanup", lambda temp_slug: cleaned.append(temp_slug))

    def fake_eval_combo(tenant_slug, queries_path, top_k, final_k, rrf_k, rerank_threshold, ks):
        evaluated.append((tenant_slug, top_k, final_k, rrf_k, rerank_threshold, tuple(ks)))
        return {
            "mean_mrr": final_k / 10,
            "recall_at_k": {"5": top_k / 10},
        }

    monkeypatch.setattr(sweep, "_eval_combo", fake_eval_combo)
    monkeypatch.setattr(
        "sys.argv",
        [
            "hyperparameter_sweep.py",
            "--tenant",
            "demo",
            "--queries",
            "eval/test_queries.json",
            "--output",
            str(output_path),
            "--top-ks",
            "3",
            "5",
            "--final-ks",
            "4",
            "6",
            "--rrf-ks",
            "30",
            "--rerank-thresholds",
            "-2.0",
            "--chunk-sizes",
            "600",
            "--overlaps",
            "100",
            "--max-runs",
            "10",
            "--ks",
            "1",
            "5",
        ],
    )

    sweep.main()

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(evaluated) == 1
    assert evaluated[0] == ("demo__sweep_cs600_ov100", 5, 4, 30, -2.0, (1, 5))
    assert indexed == [("demo", "demo__sweep_cs600_ov100", 600, 100)]
    assert cleaned == ["demo__sweep_cs600_ov100"]
    assert saved["best"][0]["top_k"] == 5
    assert saved["all_results"][0]["final_k"] == 4
