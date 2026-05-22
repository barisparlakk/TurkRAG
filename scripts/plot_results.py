"""Faz 1.4 — Deney sonuçlarını grafikle.

Reads results/*.csv or results/*.json files and produces:
  figures/metrics_comparison.png   — grouped bar chart (mode × metric)
  figures/latency_distribution.png — latency box plot (if latency data available)
  figures/recall_at_k.png          — Recall@K curve (if retrieval_metrics data available)

Usage:
  python scripts/plot_results.py [--input results/experiment_*.csv]
                                  [--output-dir figures]
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "context_precision": "Context Precision",
    "context_recall": "Context Recall",
}
MODE_COLORS = {
    "sparse": "#E07B54",
    "dense": "#5B8DB8",
    "hybrid": "#6BAF8E",
    "hybrid+rerank": "#8E6BAF",
}


def load_results(input_path: str) -> list[dict]:
    """Load results from CSV or JSON (single or list)."""
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {p}")

    if p.suffix == ".csv":
        with p.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def plot_metrics_comparison(results: list[dict], output_dir: Path) -> None:
    """Grouped bar chart: mode (x) × metric (group)."""
    import matplotlib.pyplot as plt
    import numpy as np

    valid = [r for r in results if all(_to_float(r.get(m)) is not None for m in METRICS)]
    if not valid:
        logger.warning("No valid rows for metrics comparison — skipping")
        return

    modes = [r["retrieval_mode"] for r in valid]
    n_modes = len(modes)
    n_metrics = len(METRICS)
    x = np.arange(n_modes)
    width = 0.8 / n_metrics

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, metric in enumerate(METRICS):
        values = [_to_float(r.get(metric, 0)) for r in valid]
        offset = (i - n_metrics / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=METRIC_LABELS[metric], alpha=0.85)
        for bar, val in zip(bars, values):
            if val is not None:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=7)

    ax.set_xlabel("Retrieval Mode", fontsize=12)
    ax.set_ylabel("Score (0 – 1)", fontsize=12)
    ax.set_title("TurkRAG — Retrieval Mode Comparison (RAGAS)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(modes, fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    out = output_dir / "metrics_comparison.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    logger.info("Saved: %s", out)


def plot_radar(results: list[dict], output_dir: Path) -> None:
    """Radar / spider chart for quick visual overview."""
    import matplotlib.pyplot as plt
    import numpy as np

    valid = [r for r in results if all(_to_float(r.get(m)) is not None for m in METRICS)]
    if not valid:
        return

    labels = [METRIC_LABELS[m] for m in METRICS]
    angles = np.linspace(0, 2 * np.pi, len(METRICS), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))

    for r in valid:
        mode = r["retrieval_mode"]
        values = [_to_float(r.get(m, 0)) for m in METRICS]
        values += values[:1]
        color = MODE_COLORS.get(mode, "#666666")
        ax.plot(angles, values, linewidth=2, linestyle="solid", label=mode, color=color)
        ax.fill(angles, values, alpha=0.1, color=color)

    ax.set_thetagrids(np.degrees(angles[:-1]), labels, fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_title("TurkRAG — RAGAS Radar", fontsize=13, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=9)

    out = output_dir / "metrics_radar.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    logger.info("Saved: %s", out)


def plot_recall_at_k(recall_data: list[dict], output_dir: Path) -> None:
    """Recall@K line plot from retrieval_metrics output."""
    import matplotlib.pyplot as plt

    if not recall_data:
        logger.info("No Recall@K data — skipping")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for entry in recall_data:
        mode = entry.get("retrieval_mode", "unknown")
        ks = sorted(int(k) for k in entry.get("recall_at_k", {}).keys())
        vals = [entry["recall_at_k"][str(k)] for k in ks]
        color = MODE_COLORS.get(mode, "#666666")
        ax.plot(ks, vals, marker="o", linewidth=2, label=mode, color=color)

    ax.set_xlabel("K (number of retrieved chunks)", fontsize=12)
    ax.set_ylabel("Avg. Relevant Chunks Retrieved", fontsize=12)
    ax.set_title("TurkRAG — Recall@K by Retrieval Mode", fontsize=14, fontweight="bold")
    ax.set_ylim(0, None)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    out = output_dir / "recall_at_k.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    logger.info("Saved: %s", out)


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Results Plotter")
    parser.add_argument("--input", default="", help="CSV or JSON results file")
    parser.add_argument("--recall-input", default="", help="Recall@K JSON from retrieval_metrics")
    parser.add_argument("--output-dir", default="figures")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-find latest CSV if not specified
    input_path = args.input
    if not input_path:
        candidates = sorted(Path("results").glob("experiment_*.csv"))
        if not candidates:
            candidates = sorted(Path("results").glob("*.csv"))
        if candidates:
            input_path = str(candidates[-1])
            logger.info("Auto-detected input: %s", input_path)
        else:
            logger.error("No results file found. Run scripts/run_experiments.py first.")
            sys.exit(1)

    results = load_results(input_path)
    logger.info("Loaded %d result rows", len(results))

    plot_metrics_comparison(results, output_dir)
    plot_radar(results, output_dir)

    if args.recall_input:
        raw = json.loads(Path(args.recall_input).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            raw = [raw]
        # Support both flat and nested {"aggregate": {...}} structure
        recall_data = []
        for entry in raw:
            if "aggregate" in entry:
                recall_data.append(entry["aggregate"])
            else:
                recall_data.append(entry)
        plot_recall_at_k(recall_data, output_dir)

    logger.info("All plots saved to %s/", output_dir)


if __name__ == "__main__":
    sys.exit(main())
