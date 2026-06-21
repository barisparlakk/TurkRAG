"""Faz 1.3 — Tüm retrieval mode'larını sırayla çalıştırıp sonuçları karşılaştır.

Usage:
  python scripts/run_experiments.py --tenant demo [--queries eval/test_queries.json]
                                    [--top-k 20] [--final-k 5] [--save-db]
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path when script is run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

MODES = ["sparse", "dense", "hybrid", "hybrid+rerank"]
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
RETRIEVAL_METRICS = [
    "mean_mrr",
    "mean_ap",
    "recall@1",
    "recall@3",
    "recall@5",
    "ndcg@1",
    "ndcg@3",
    "ndcg@5",
]
LATENCY_FIELDS = ["retrieval_latency_ms", "generation_latency_ms", "total_latency_ms"]


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Retrieval Mode Comparison")
    parser.add_argument("--tenant", required=True, help="Tenant slug")
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--modes", nargs="+", default=MODES,
                        choices=MODES, help="Modes to run (default: all 4)")
    parser.add_argument("--save-db", action="store_true")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    from eval.ragas_eval import run_eval, save_to_db

    all_results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for mode in args.modes:
        logger.info("=" * 60)
        logger.info("Running mode: %s", mode)
        logger.info("=" * 60)
        try:
            scores = run_eval(
                tenant_slug=args.tenant,
                queries_path=args.queries,
                retrieval_mode=mode,
                top_k=args.top_k,
                final_k=args.final_k,
                run_label=f"{mode}-top{args.top_k}-final{args.final_k}",
            )
            all_results.append(scores)

            if args.save_db:
                save_to_db(scores)

            mode_file = output_dir / f"{timestamp}_{mode.replace('+', '_')}.json"
            mode_file.write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Saved: %s", mode_file)

        except Exception as exc:
            logger.error("Mode '%s' failed: %s", mode, exc)
            all_results.append({"retrieval_mode": mode, "error": str(exc)})

    # Summary CSV
    try:
        import csv
        csv_path = output_dir / f"experiment_{timestamp}.csv"
        fieldnames = (
            ["retrieval_mode", "run_label"]
            + METRICS
            + RETRIEVAL_METRICS
            + LATENCY_FIELDS
            + ["n_queries", "top_k", "final_k", "evaluated_at"]
        )
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_results)
        logger.info("Summary CSV: %s", csv_path)
    except Exception as exc:
        logger.warning("Could not write CSV: %s", exc)

    # Print comparison table
    print("\n" + "=" * 75)
    print(f"  {'Mode':<18}", end="")
    for m in METRICS:
        print(f"  {m[:12]:<13}", end="")
    print()
    print("=" * 75)
    for r in all_results:
        if "error" in r:
            print(f"  {r['retrieval_mode']:<18}  ERROR: {r['error'][:40]}")
            continue
        print(f"  {r['retrieval_mode']:<18}", end="")
        for m in METRICS:
            val = r.get(m, float("nan"))
            print(f"  {val:<13.3f}", end="")
        print()
    print("=" * 75)

    # Best mode per metric
    valid = [r for r in all_results if "error" not in r]
    if valid:
        print("\n  Best per metric:")
        for m in METRICS + RETRIEVAL_METRICS:
            best = max(valid, key=lambda r: r.get(m, 0))
            print(f"    {m:<22} → {best['retrieval_mode']} ({best[m]:.3f})")
    print()


if __name__ == "__main__":
    sys.exit(main())
