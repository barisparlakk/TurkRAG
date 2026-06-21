"""Faz 2.3 — Retrieval quality metrics: Recall@K, MRR, nDCG.

Evaluates retrieval independently of generation, using a ground-truth
relevance mapping (relevant_docs per query).

Input JSON format (eval/test_queries.json extended, or eval_set_generated.json):
  [{"question": "...", "ground_truth": "...", "relevant_doc": "filename.pdf"}, ...]

Usage:
  python -m eval.retrieval_metrics --tenant demo
                                   [--queries eval/test_queries.json]
                                   [--ks 1 3 5 10 20]
                                   [--modes sparse dense hybrid hybrid+rerank]
                                   [--output results/retrieval_metrics.json]
"""

import argparse
import json
import logging
import math
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_KS = [1, 3, 5, 10, 20]


# ── Core metric functions ──────────────────────────────────────────────────────

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant docs found in the top-k retrieved."""
    if not relevant:
        return 0.0
    hits = len(set(retrieved[:k]) & relevant)
    return hits / len(relevant)


def mean_reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant hit; 0 if none found."""
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at K (binary document relevance)."""
    seen_relevant = set()
    dcg = 0.0
    for rank, doc in enumerate(retrieved[:k], start=1):
        if doc in relevant and doc not in seen_relevant:
            dcg += 1.0 / math.log2(rank + 1)
            seen_relevant.add(doc)
    # Ideal DCG: all relevant docs at top positions
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of top-k retrieved docs that are relevant."""
    if k == 0:
        return 0.0
    hits = len(set(retrieved[:k]) & relevant)
    return hits / k


def average_precision(retrieved: list[str], relevant: set[str]) -> float:
    """Area under the Precision-Recall curve (AP)."""
    if not relevant:
        return 0.0
    hits = 0
    total_precision = 0.0
    seen_relevant = set()
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant and doc not in seen_relevant:
            hits += 1
            total_precision += hits / rank
            seen_relevant.add(doc)
    return total_precision / len(relevant)


# ── Evaluation runner ──────────────────────────────────────────────────────────

def evaluate_retrieval(
    tenant_slug: str,
    queries_path: str,
    mode: str = "hybrid+rerank",
    ks: list[int] | None = None,
    top_k: int = 20,
    final_k: int = 20,
) -> dict:
    """Run retrieval for each query, compute metrics, return results dict."""
    from retrieval.hybrid import HybridRetriever

    ks = ks or DEFAULT_KS
    max_k = max(ks)

    queries_file = Path(queries_path)
    if not queries_file.exists():
        raise FileNotFoundError(f"Queries file not found: {queries_file}")

    test_queries = json.loads(queries_file.read_text(encoding="utf-8"))
    logger.info("Loaded %d queries from %s [mode=%s]", len(test_queries), queries_file, mode)

    retriever = HybridRetriever()

    per_query: list[dict] = []
    for i, item in enumerate(test_queries):
        question = item["question"]
        # Support single relevant_doc string or a list
        rel_raw = item.get("relevant_doc", item.get("relevant_docs", ""))
        if isinstance(rel_raw, str):
            relevant = {rel_raw} if rel_raw else set()
        else:
            relevant = set(rel_raw)

        chunks = retriever.retrieve(
            question, tenant_slug,
            top_k=max(top_k, max_k),
            final_k=max(final_k, max_k),
            mode=mode,
        )
        retrieved_docs = [c.get("filename", "") for c in chunks]

        entry = {
            "question": question,
            "relevant_docs": list(relevant),
            "retrieved_docs": retrieved_docs,
            "mrr": mean_reciprocal_rank(retrieved_docs, relevant),
            "ap": average_precision(retrieved_docs, relevant),
        }
        for k in ks:
            entry[f"recall@{k}"] = recall_at_k(retrieved_docs, relevant, k)
            entry[f"precision@{k}"] = precision_at_k(retrieved_docs, relevant, k)
            entry[f"ndcg@{k}"] = ndcg_at_k(retrieved_docs, relevant, k)

        per_query.append(entry)
        logger.info(
            "[%d/%d] MRR=%.3f  Recall@5=%.3f  nDCG@5=%.3f  — %s",
            i + 1, len(test_queries),
            entry["mrr"], entry.get("recall@5", 0.0), entry.get("ndcg@5", 0.0),
            question[:60],
        )

    # Aggregate
    n = len(per_query)
    aggregate: dict = {
        "retrieval_mode": mode,
        "tenant_slug": tenant_slug,
        "n_queries": n,
        "top_k": top_k,
        "final_k": final_k,
        "evaluated_at": datetime.now().isoformat(),
        "mean_mrr": sum(e["mrr"] for e in per_query) / n if n else 0.0,
        "mean_ap": sum(e["ap"] for e in per_query) / n if n else 0.0,
        "recall_at_k": {},
        "precision_at_k": {},
        "ndcg_at_k": {},
    }
    for k in ks:
        aggregate["recall_at_k"][str(k)] = sum(e[f"recall@{k}"] for e in per_query) / n if n else 0.0
        aggregate["precision_at_k"][str(k)] = sum(e[f"precision@{k}"] for e in per_query) / n if n else 0.0
        aggregate["ndcg_at_k"][str(k)] = sum(e[f"ndcg@{k}"] for e in per_query) / n if n else 0.0

    return {"aggregate": aggregate, "per_query": per_query}


def _print_table(results: list[dict], ks: list[int]) -> None:
    print("\n" + "=" * 80)
    print(f"  {'Mode':<18}  {'MRR':>6}  {'MAP':>6}", end="")
    for k in ks:
        print(f"  {'R@' + str(k):>6}", end="")
    print()
    print("=" * 80)
    for r in results:
        agg = r["aggregate"]
        print(f"  {agg['retrieval_mode']:<18}  {agg['mean_mrr']:>6.3f}  {agg['mean_ap']:>6.3f}", end="")
        for k in ks:
            print(f"  {agg['recall_at_k'].get(str(k), 0):>6.3f}", end="")
        print()
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Retrieval Metrics (Recall@K, MRR, nDCG)")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--modes", nargs="+", default=["hybrid+rerank"],
                        choices=["sparse", "dense", "hybrid", "hybrid+rerank"])
    parser.add_argument("--ks", nargs="+", type=int, default=DEFAULT_KS,
                        help="K values for Recall@K, nDCG@K")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=20,
                        help="Set equal to max K so all ranks are visible")
    parser.add_argument("--output", default="results/retrieval_metrics.json")
    args = parser.parse_args()

    all_results = []
    for mode in args.modes:
        logger.info("=" * 60)
        logger.info("Evaluating retrieval: mode=%s", mode)
        logger.info("=" * 60)
        try:
            result = evaluate_retrieval(
                tenant_slug=args.tenant,
                queries_path=args.queries,
                mode=mode,
                ks=args.ks,
                top_k=args.top_k,
                final_k=args.final_k,
            )
            all_results.append(result)
        except Exception as exc:
            logger.error("Mode '%s' failed: %s", mode, exc)

    _print_table(all_results, args.ks)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved: %s", out)


if __name__ == "__main__":
    import sys
    sys.exit(main())
