"""Faz 4.4 — Compare embedding models on retrieval quality.

For each local model under models/, re-embeds the tenant's chunks into a
temporary Qdrant collection, then evaluates Recall@K using the existing
retrieval_metrics pipeline (dense mode, since only the embedder changes).

BM25 indexes are unchanged — only dense retrieval is affected.

Usage:
  python scripts/embedder_experiments.py --tenant demo
                                          [--models turkish-embedder paraphrase-multilingual]
                                          [--queries eval/test_queries.json]
                                          [--ks 1 3 5 10]
                                          [--output results/embedder_experiments.json]

Pre-requisites: at least two local model dirs under models/
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


def load_chunks_from_bm25(tenant_slug: str) -> tuple[list[str], list[dict]]:
    """Return (texts, payloads) from the production BM25 pickle."""
    import pickle
    bm25_path = Path("indexes") / f"bm25_{tenant_slug}.pkl"
    if not bm25_path.exists():
        raise FileNotFoundError(f"BM25 index not found: {bm25_path}")
    with bm25_path.open("rb") as f:
        data = pickle.load(f)
    return data["texts"], data["payloads"]


def build_temp_qdrant(
    texts: list[str],
    payloads: list[dict],
    model_path: str,
    temp_tenant: str,
) -> None:
    """Embed texts with *model_path* and upsert into a temp Qdrant collection."""
    from ingestion.embedder import embed
    from retrieval.vector_store import VectorStore

    BATCH = 32
    vstore = VectorStore(temp_tenant)
    for i in range(0, len(texts), BATCH):
        batch_texts = texts[i:i + BATCH]
        batch_payloads = payloads[i:i + BATCH]
        vecs = embed(batch_texts, model_path=model_path)
        vstore.upsert(vecs.tolist(), batch_payloads)

    logger.info("Indexed %d chunks into temp tenant '%s' using model '%s'",
                len(texts), temp_tenant, model_path)


def evaluate_embedder(
    temp_tenant: str,
    queries_path: str,
    model_path: str,
    ks: list[int],
) -> dict:
    """Evaluate dense retrieval with the temp tenant (which uses the experiment embedder)."""
    # Set env var so HybridRetriever's embed() calls use the experiment model
    old_env = os.environ.get("EMBEDDING_MODEL")
    os.environ["EMBEDDING_MODEL"] = model_path
    try:
        from eval.retrieval_metrics import evaluate_retrieval
        result = evaluate_retrieval(
            tenant_slug=temp_tenant,
            queries_path=queries_path,
            mode="dense",
            ks=ks,
            top_k=max(ks) + 5,
            final_k=max(ks),
        )
        return result["aggregate"]
    finally:
        if old_env is None:
            os.environ.pop("EMBEDDING_MODEL", None)
        else:
            os.environ["EMBEDDING_MODEL"] = old_env


def cleanup_temp_qdrant(temp_tenant: str) -> None:
    try:
        from retrieval.vector_store import VectorStore
        VectorStore(temp_tenant).delete_collection()
        logger.info("Deleted temp Qdrant collection: %s", temp_tenant)
    except Exception as exc:
        logger.warning("Could not delete temp collection '%s': %s", temp_tenant, exc)


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Embedder Comparison")
    parser.add_argument("--tenant", required=True)
    parser.add_argument(
        "--models", nargs="+", default=None,
        help="Model dir names under models/. Defaults to all dirs found there.",
    )
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10])
    parser.add_argument("--output", default="results/embedder_experiments.json")
    parser.add_argument("--no-cleanup", action="store_true")
    args = parser.parse_args()

    from ingestion.embedder import list_available_models
    model_names = args.models or list_available_models()
    if not model_names:
        logger.error("No models found under models/. Specify --models or add model dirs.")
        sys.exit(1)
    logger.info("Models to evaluate: %s", model_names)

    texts, payloads = load_chunks_from_bm25(args.tenant)
    results = []

    for model_name in model_names:
        model_path = str(Path("models") / model_name)
        temp_tenant = f"{args.tenant}__emb_exp_{model_name.replace('/', '_')}"
        logger.info("=" * 60)
        logger.info("Embedder: %s → temp tenant: %s", model_name, temp_tenant)
        logger.info("=" * 60)
        try:
            build_temp_qdrant(texts, payloads, model_path, temp_tenant)
            agg = evaluate_embedder(temp_tenant, args.queries, model_path, args.ks)
            agg["embedder"] = model_name
            agg["model_path"] = model_path
            results.append(agg)
        except Exception as exc:
            logger.error("Embedder '%s' failed: %s", model_name, exc)
            results.append({"embedder": model_name, "error": str(exc)})
        finally:
            if not args.no_cleanup:
                cleanup_temp_qdrant(temp_tenant)

    # Print comparison table
    print("\n" + "=" * 70)
    print(f"  {'Embedder':<30}  {'MRR':>6}", end="")
    for k in args.ks:
        print(f"  {'R@' + str(k):>6}", end="")
    print()
    print("=" * 70)
    for r in results:
        if "error" in r:
            print(f"  {r['embedder']:<30}  ERROR: {r['error'][:30]}")
            continue
        print(f"  {r['embedder']:<30}  {r.get('mean_mrr', 0):>6.3f}", end="")
        for k in args.ks:
            print(f"  {r.get('recall_at_k', {}).get(str(k), 0):>6.3f}", end="")
        print()
    print("=" * 70 + "\n")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved: %s", out)


if __name__ == "__main__":
    sys.exit(main())
