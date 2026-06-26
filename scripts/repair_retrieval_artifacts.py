"""Recompute normalized retrieval metrics inside committed JSON artifacts.

Usage:
  python scripts/repair_retrieval_artifacts.py
  python scripts/repair_retrieval_artifacts.py --paths results/retrieval_metrics.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.retrieval_metrics import (
    DEFAULT_KS,
    average_precision,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from scripts.audit_retrieval_artifacts import DEFAULT_PATHS

QUESTION_SOURCE_BY_COUNT = {
    47: ROOT / "eval" / "eval_set_generated.csv",
}


def _ks_for_result(result: dict) -> list[int]:
    aggregate = result.get("aggregate", {})
    recall_group = aggregate.get("recall_at_k", {})
    ks: set[int] = set()
    if isinstance(recall_group, dict):
        for key in recall_group:
            try:
                ks.add(int(key))
            except (TypeError, ValueError):
                continue
    if not ks:
        ks.update(DEFAULT_KS)
    return sorted(ks)


def _question_backfill_rows(query_count: int) -> list[dict[str, str]]:
    source_path = QUESTION_SOURCE_BY_COUNT.get(query_count)
    if source_path is None or not source_path.exists():
        return []
    with source_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows if len(rows) == query_count else []


def repair_retrieval_artifact(path: str | Path) -> None:
    artifact_path = Path(path)
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{artifact_path} must contain a top-level list")

    repaired_results: list[dict] = []
    for result in payload:
        aggregate = dict(result.get("aggregate") or {})
        per_query = []
        ks = _ks_for_result(result)
        question_rows = _question_backfill_rows(len(result.get("per_query", [])))

        for index, raw_query in enumerate(result.get("per_query", [])):
            query = dict(raw_query)
            retrieved_docs = [str(doc) for doc in query.get("retrieved_docs", [])]
            relevant_docs = {str(doc) for doc in query.get("relevant_docs", []) if doc}
            if not str(query.get("question", "")).strip() and index < len(question_rows):
                backfilled_question = question_rows[index].get("question", "")
                if backfilled_question:
                    query["question"] = backfilled_question

            query["mrr"] = mean_reciprocal_rank(retrieved_docs, relevant_docs)
            query["ap"] = average_precision(retrieved_docs, relevant_docs)
            for k in ks:
                query[f"recall@{k}"] = recall_at_k(retrieved_docs, relevant_docs, k)
                query[f"precision@{k}"] = precision_at_k(retrieved_docs, relevant_docs, k)
                query[f"ndcg@{k}"] = ndcg_at_k(retrieved_docs, relevant_docs, k)
            per_query.append(query)

        n_queries = len(per_query)
        aggregate["n_queries"] = n_queries
        aggregate["mean_mrr"] = sum(query["mrr"] for query in per_query) / n_queries if n_queries else 0.0
        aggregate["mean_ap"] = sum(query["ap"] for query in per_query) / n_queries if n_queries else 0.0
        aggregate["recall_at_k"] = {
            str(k): (sum(query[f"recall@{k}"] for query in per_query) / n_queries if n_queries else 0.0)
            for k in ks
        }
        aggregate["precision_at_k"] = {
            str(k): (sum(query[f"precision@{k}"] for query in per_query) / n_queries if n_queries else 0.0)
            for k in ks
        }
        aggregate["ndcg_at_k"] = {
            str(k): (sum(query[f"ndcg@{k}"] for query in per_query) / n_queries if n_queries else 0.0)
            for k in ks
        }
        repaired_results.append({"aggregate": aggregate, "per_query": per_query})

    artifact_path.write_text(
        json.dumps(repaired_results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair stale retrieval metric artifacts in place")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=list(DEFAULT_PATHS),
        help="Artifact paths to rewrite in place (default: committed retrieval_metrics*.json files)",
    )
    args = parser.parse_args()

    for raw_path in args.paths:
        repair_retrieval_artifact(raw_path)
        print(f"Repaired: {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
