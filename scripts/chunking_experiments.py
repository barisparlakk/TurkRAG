"""Faz 4.2 — Compare chunking strategies on Recall@5.

For each strategy, re-ingests the tenant's raw documents using that chunker,
rebuilds temporary BM25 and Qdrant indexes, then evaluates Recall@5 using
the existing retrieval_metrics pipeline.

IMPORTANT: This script operates on *temporary* indexes. The production tenant
indexes are NOT modified. The tenant slug used for temp indexes is
  "<tenant_slug>__chunk_exp_<strategy>"

Usage:
  python scripts/chunking_experiments.py --tenant demo
                                          [--strategies turkish fixed recursive paragraph]
                                          [--queries eval/test_queries.json]
                                          [--mode hybrid+rerank]
                                          [--output results/chunking_experiments.json]

Pre-requisites:
  - Raw document texts stored in PostgreSQL (documents.raw_text column), OR
  - Pre-chunked BM25 pickle exists for the tenant and texts are loaded from it.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

STRATEGIES = ["turkish", "fixed", "recursive", "paragraph"]
STRATEGY_CONFIGS = {
    "turkish":   {"max_chars": 800, "overlap_chars": 150},
    "fixed":     {"max_chars": 800, "overlap_chars": 150},
    "recursive": {"max_chars": 800, "overlap_chars": 150},
    "paragraph": {"max_chars": 800, "overlap_chars": 0},
}


def load_raw_texts_from_bm25(tenant_slug: str) -> list[tuple[str, dict]]:
    """Load (text, payload) pairs from the existing BM25 pickle.

    Each unique doc_id is loaded once — chunks are reconstructed at the
    document level by joining chunk texts in order.
    """
    import pickle
    bm25_path = Path("indexes") / f"bm25_{tenant_slug}.pkl"
    if not bm25_path.exists():
        raise FileNotFoundError(f"BM25 index not found: {bm25_path}")
    with bm25_path.open("rb") as f:
        data = pickle.load(f)

    docs: dict[str, dict] = {}
    for text, payload in zip(data["texts"], data["payloads"], strict=False):
        doc_id = payload.get("doc_id", "")
        if doc_id not in docs:
            docs[doc_id] = {"text": "", "payload": payload, "chunks": []}
        docs[doc_id]["chunks"].append((payload.get("chunk_index", 0), text))

    result = []
    for _doc_id, doc in docs.items():
        ordered = sorted(doc["chunks"], key=lambda x: x[0])
        full_text = "\n\n".join(t for _, t in ordered)
        result.append((full_text, doc["payload"]))

    logger.info("Loaded %d documents from %s", len(result), bm25_path)
    return result


def rechunk_and_index(
    docs: list[tuple[str, dict]],
    strategy: str,
    temp_tenant: str,
) -> None:
    """Chunk documents with the given strategy and build temp BM25 + Qdrant indexes."""
    from ingestion.chunker import get_chunker
    from ingestion.embedder import embed
    from retrieval.bm25_store import BM25Store
    from retrieval.vector_store import VectorStore

    config = STRATEGY_CONFIGS.get(strategy, {})
    chunker = get_chunker(strategy, **config)

    all_texts = []
    all_payloads = []
    for full_text, base_payload in docs:
        chunks = chunker.chunk(full_text)
        for chunk in chunks:
            payload = {
                **base_payload,
                "chunk_index": chunk["chunk_index"],
                "start_char": chunk.get("start_char", 0),
                "end_char": chunk.get("end_char", 0),
                "chunker": strategy,
            }
            all_texts.append(chunk["text"])
            all_payloads.append(payload)

    logger.info("Strategy '%s': %d total chunks from %d docs", strategy, len(all_texts), len(docs))

    # Build temp BM25
    bm25_store = BM25Store(temp_tenant)
    bm25_store.build(all_texts, all_payloads)

    # Build temp Qdrant (embed in batches)
    BATCH = 32
    for i in range(0, len(all_texts), BATCH):
        batch_texts = all_texts[i:i + BATCH]
        batch_payloads = all_payloads[i:i + BATCH]
        vecs = embed(batch_texts)
        VectorStore(temp_tenant).upsert(vecs.tolist(), batch_payloads)

    logger.info("Indexed %d chunks for temp tenant '%s'", len(all_texts), temp_tenant)


def evaluate_strategy(
    temp_tenant: str,
    queries_path: str,
    mode: str,
    ks: list[int],
) -> dict:
    """Run retrieval_metrics against the temp tenant index."""
    from eval.retrieval_metrics import evaluate_retrieval
    result = evaluate_retrieval(
        tenant_slug=temp_tenant,
        queries_path=queries_path,
        mode=mode,
        ks=ks,
        top_k=max(ks) + 5,
        final_k=max(ks),
    )
    return result["aggregate"]


def cleanup_temp_tenant(temp_tenant: str) -> None:
    """Remove temp BM25 pickle and Qdrant collection."""
    bm25_path = Path("indexes") / f"bm25_{temp_tenant}.pkl"
    if bm25_path.exists():
        bm25_path.unlink()
        logger.info("Removed temp BM25: %s", bm25_path)
    try:
        from retrieval.vector_store import VectorStore
        VectorStore(temp_tenant).delete_collection()
        logger.info("Deleted temp Qdrant collection: %s", temp_tenant)
    except Exception as exc:
        logger.warning("Could not delete temp Qdrant collection: %s", exc)


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Chunking Strategy Comparison")
    parser.add_argument("--tenant", required=True, help="Source tenant slug")
    parser.add_argument("--strategies", nargs="+", default=STRATEGIES, choices=STRATEGIES)
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--mode", default="hybrid+rerank",
                        choices=["sparse", "dense", "hybrid", "hybrid+rerank"])
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--output", default="results/chunking_experiments.json")
    parser.add_argument("--no-cleanup", action="store_true",
                        help="Keep temp indexes for debugging")
    args = parser.parse_args()

    docs = load_raw_texts_from_bm25(args.tenant)
    results = []

    for strategy in args.strategies:
        temp_tenant = f"{args.tenant}__chunk_exp_{strategy}"
        logger.info("=" * 60)
        logger.info("Strategy: %s → temp tenant: %s", strategy, temp_tenant)
        logger.info("=" * 60)
        try:
            rechunk_and_index(docs, strategy, temp_tenant)
            agg = evaluate_strategy(temp_tenant, args.queries, args.mode, args.ks)
            agg["chunker_strategy"] = strategy
            agg["chunker_config"] = STRATEGY_CONFIGS.get(strategy, {})
            results.append(agg)
        except Exception as exc:
            logger.error("Strategy '%s' failed: %s", strategy, exc)
            results.append({"chunker_strategy": strategy, "error": str(exc)})
        finally:
            if not args.no_cleanup:
                cleanup_temp_tenant(temp_tenant)

    # Print comparison table
    print("\n" + "=" * 75)
    print(f"  {'Strategy':<12}  {'MRR':>6}", end="")
    for k in args.ks:
        print(f"  {'R@' + str(k):>6}", end="")
    print()
    print("=" * 75)
    for r in results:
        if "error" in r:
            print(f"  {r['chunker_strategy']:<12}  ERROR: {r['error'][:40]}")
            continue
        print(f"  {r['chunker_strategy']:<12}  {r.get('mean_mrr', 0):>6.3f}", end="")
        for k in args.ks:
            print(f"  {r.get('recall_at_k', {}).get(str(k), 0):>6.3f}", end="")
        print()
    print("=" * 75 + "\n")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved: %s", out)


if __name__ == "__main__":
    sys.exit(main())
