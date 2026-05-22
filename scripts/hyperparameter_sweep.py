"""Faz 5 — Grid search over RAG hyperparameters.

Sweeps combinations of:
  top_k           : candidates fetched before reranking
  final_k         : chunks fed to LLM
  rrf_k           : RRF constant (fusion smoothing)
  rerank_threshold: cross-encoder confidence gate
  chunk_size      : TurkishChunker MAX_CHARS
  overlap         : TurkishChunker OVERLAP_CHARS

For each combination, re-indexes the tenant (if chunk_size/overlap changed)
and evaluates Recall@5 + MRR via retrieval_metrics (dense mode skipped for
speed — hybrid+rerank is the target).

Usage:
  python scripts/hyperparameter_sweep.py --tenant demo
                                          [--queries eval/test_queries.json]
                                          [--output results/hyperparameter_sweep.json]
                                          [--top-ks 10 20]
                                          [--final-ks 3 5]
                                          [--rrf-ks 30 60 120]
                                          [--rerank-thresholds -4.0 -2.0 0.0]
                                          [--chunk-sizes 600 800]
                                          [--overlaps 100 150]
                                          [--max-runs 50]
"""

import argparse
import itertools
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


def _rechunk_and_index(tenant: str, temp_slug: str, chunk_size: int, overlap: int) -> None:
    """Rebuild BM25 + Qdrant indexes for a given chunk_size/overlap pair."""
    import pickle
    from ingestion.chunker import get_chunker
    from ingestion.embedder import embed
    from retrieval.bm25_store import BM25Store
    from retrieval.vector_store import VectorStore

    bm25_path = Path("indexes") / f"bm25_{tenant}.pkl"
    with bm25_path.open("rb") as f:
        data = pickle.load(f)

    # Reconstruct full doc texts
    docs: dict[str, dict] = {}
    for text, payload in zip(data["texts"], data["payloads"]):
        doc_id = payload.get("doc_id", "")
        if doc_id not in docs:
            docs[doc_id] = {"chunks": [], "payload": payload}
        docs[doc_id]["chunks"].append((payload.get("chunk_index", 0), text))

    chunker = get_chunker("turkish", max_chars=chunk_size, overlap_chars=overlap)
    all_texts, all_payloads = [], []
    for doc_id, doc in docs.items():
        ordered = sorted(doc["chunks"], key=lambda x: x[0])
        full_text = "\n\n".join(t for _, t in ordered)
        for chunk in chunker.chunk(full_text):
            payload = {**doc["payload"], "chunk_index": chunk["chunk_index"]}
            all_texts.append(chunk["text"])
            all_payloads.append(payload)

    BM25Store(temp_slug).build(all_texts, all_payloads)
    BATCH = 32
    for i in range(0, len(all_texts), BATCH):
        vecs = embed(all_texts[i:i + BATCH])
        VectorStore(temp_slug).upsert(vecs.tolist(), all_payloads[i:i + BATCH])
    logger.info("Re-indexed %d chunks into '%s' (chunk_size=%d, overlap=%d)",
                len(all_texts), temp_slug, chunk_size, overlap)


def _cleanup(temp_slug: str) -> None:
    bm25_path = Path("indexes") / f"bm25_{temp_slug}.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
    try:
        from retrieval.vector_store import VectorStore
        VectorStore(temp_slug).delete_collection()
    except Exception:
        pass


def _eval_combo(
    tenant_slug: str,
    queries_path: str,
    top_k: int,
    final_k: int,
    rrf_k: int,
    rerank_threshold: float,
    ks: list[int] = None,
) -> dict:
    """Run retrieval_metrics with patched module-level constants."""
    import retrieval.hybrid as hybrid_mod
    from eval.retrieval_metrics import evaluate_retrieval

    old_rrf = hybrid_mod.RRF_K
    old_threshold = hybrid_mod.CONFIDENCE_THRESHOLD

    hybrid_mod.RRF_K = rrf_k
    hybrid_mod.CONFIDENCE_THRESHOLD = rerank_threshold
    try:
        result = evaluate_retrieval(
            tenant_slug=tenant_slug,
            queries_path=queries_path,
            mode="hybrid+rerank",
            ks=ks or [1, 3, 5, 10],
            top_k=top_k,
            final_k=final_k,
        )
        return result["aggregate"]
    finally:
        hybrid_mod.RRF_K = old_rrf
        hybrid_mod.CONFIDENCE_THRESHOLD = old_threshold


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Hyperparameter Sweep")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--output", default="results/hyperparameter_sweep.json")
    parser.add_argument("--top-ks", nargs="+", type=int, default=[10, 20])
    parser.add_argument("--final-ks", nargs="+", type=int, default=[3, 5])
    parser.add_argument("--rrf-ks", nargs="+", type=int, default=[30, 60, 120])
    parser.add_argument("--rerank-thresholds", nargs="+", type=float, default=[-4.0, -2.0, 0.0])
    parser.add_argument("--chunk-sizes", nargs="+", type=int, default=[600, 800])
    parser.add_argument("--overlaps", nargs="+", type=int, default=[100, 150])
    parser.add_argument("--max-runs", type=int, default=50,
                        help="Cap total combinations (random sample if exceeded)")
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--no-cleanup", action="store_true")
    args = parser.parse_args()

    combos = list(itertools.product(
        args.top_ks, args.final_ks, args.rrf_ks,
        args.rerank_thresholds, args.chunk_sizes, args.overlaps,
    ))

    # Filter invalid combos (final_k must be <= top_k)
    combos = [(tk, fk, rk, rt, cs, ov) for tk, fk, rk, rt, cs, ov in combos if fk <= tk]

    if len(combos) > args.max_runs:
        import random
        random.seed(42)
        combos = random.sample(combos, args.max_runs)
        logger.info("Sampled %d / %d combinations", args.max_runs, len(combos))
    else:
        logger.info("Total combinations: %d", len(combos))

    results = []
    # Track which chunk configs are already indexed
    indexed: dict[tuple[int, int], str] = {}

    for i, (top_k, final_k, rrf_k, rerank_threshold, chunk_size, overlap) in enumerate(combos):
        chunk_key = (chunk_size, overlap)
        if chunk_key not in indexed:
            temp_slug = f"{args.tenant}__sweep_cs{chunk_size}_ov{overlap}"
            try:
                _rechunk_and_index(args.tenant, temp_slug, chunk_size, overlap)
                indexed[chunk_key] = temp_slug
            except Exception as exc:
                logger.error("Indexing failed for chunk_size=%d overlap=%d: %s",
                             chunk_size, overlap, exc)
                continue
        else:
            temp_slug = indexed[chunk_key]

        logger.info(
            "[%d/%d] top_k=%d final_k=%d rrf_k=%d threshold=%.1f chunk=%d overlap=%d",
            i + 1, len(combos), top_k, final_k, rrf_k, rerank_threshold, chunk_size, overlap,
        )
        try:
            agg = _eval_combo(temp_slug, args.queries, top_k, final_k, rrf_k,
                              rerank_threshold, args.ks)
            agg.update({
                "top_k": top_k,
                "final_k": final_k,
                "rrf_k": rrf_k,
                "rerank_threshold": rerank_threshold,
                "chunk_size": chunk_size,
                "overlap": overlap,
            })
            results.append(agg)
            r5 = agg.get("recall_at_k", {}).get("5", 0.0)
            mrr = agg.get("mean_mrr", 0.0)
            logger.info("  → Recall@5=%.3f  MRR=%.3f", r5, mrr)
        except Exception as exc:
            logger.error("  Eval failed: %s", exc)
            results.append({
                "top_k": top_k, "final_k": final_k, "rrf_k": rrf_k,
                "rerank_threshold": rerank_threshold,
                "chunk_size": chunk_size, "overlap": overlap,
                "error": str(exc),
            })

    if not args.no_cleanup:
        for temp_slug in indexed.values():
            _cleanup(temp_slug)

    # Sort by Recall@5 descending
    valid = [r for r in results if "error" not in r]
    valid.sort(key=lambda r: r.get("recall_at_k", {}).get("5", 0), reverse=True)

    # Print top-10
    print("\n" + "=" * 80)
    print("  TOP-10 CONFIGURATIONS by Recall@5")
    print(f"  {'top_k':>5}  {'final_k':>7}  {'rrf_k':>5}  {'thresh':>6}  "
          f"{'cs':>4}  {'ov':>4}  {'R@5':>5}  {'MRR':>5}")
    print("=" * 80)
    for r in valid[:10]:
        print(f"  {r['top_k']:>5}  {r['final_k']:>7}  {r['rrf_k']:>5}  "
              f"{r['rerank_threshold']:>6.1f}  {r['chunk_size']:>4}  {r['overlap']:>4}  "
              f"{r.get('recall_at_k', {}).get('5', 0):>5.3f}  "
              f"{r.get('mean_mrr', 0):>5.3f}")
    print("=" * 80 + "\n")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "best": valid[:10] if valid else [],
        "all_results": results,
        "evaluated_at": datetime.now().isoformat(),
    }
    out.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved: %s (%d runs)", out, len(results))


if __name__ == "__main__":
    sys.exit(main())
