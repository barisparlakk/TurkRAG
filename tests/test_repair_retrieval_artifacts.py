import json

import pytest

from scripts.repair_retrieval_artifacts import repair_retrieval_artifact


def test_repair_retrieval_artifact_recomputes_duplicate_document_metrics(tmp_path):
    artifact_path = tmp_path / "retrieval_metrics_1q.json"
    artifact_path.write_text(json.dumps([{
        "aggregate": {
            "retrieval_mode": "hybrid",
            "tenant_slug": "demo",
            "n_queries": 1,
            "top_k": 20,
            "final_k": 20,
            "evaluated_at": "2026-06-26T00:00:00",
            "mean_mrr": 2.0,
            "mean_ap": 2.0,
            "recall_at_k": {"1": 2.0, "3": 3.0},
            "precision_at_k": {"1": 1.0, "3": 1.0},
            "ndcg_at_k": {"1": 2.0, "3": 2.0},
        },
        "per_query": [{
            "question": "Soru",
            "relevant_docs": ["doc-a", "doc-b"],
            "retrieved_docs": ["doc-a", "doc-a", "doc-b"],
            "mrr": 99.0,
            "ap": 99.0,
            "recall@1": 99.0,
            "precision@1": 99.0,
            "ndcg@1": 99.0,
            "recall@3": 99.0,
            "precision@3": 99.0,
            "ndcg@3": 99.0,
        }],
    }]), encoding="utf-8")

    repair_retrieval_artifact(artifact_path)

    repaired = json.loads(artifact_path.read_text(encoding="utf-8"))
    query = repaired[0]["per_query"][0]
    aggregate = repaired[0]["aggregate"]

    assert query["mrr"] == 1.0
    assert query["ap"] == pytest.approx(5 / 6)
    assert query["recall@1"] == 0.5
    assert query["recall@3"] == 1.0
    assert query["precision@3"] == pytest.approx(2 / 3)
    assert query["ndcg@3"] == pytest.approx(0.9197207891481876)
    assert aggregate["mean_ap"] == pytest.approx(5 / 6)
    assert aggregate["recall_at_k"]["1"] == 0.5
    assert aggregate["recall_at_k"]["3"] == 1.0
