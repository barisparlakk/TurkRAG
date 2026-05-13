"""RAGAS evaluation pipeline for TurkRAG.

Evaluates retrieval and generation quality using the RAGAS framework.

Metrics:
  - faithfulness:       Is the answer grounded in the retrieved context?
  - answer_relevancy:   Does the answer address the question?
  - context_precision:  Are the retrieved chunks relevant?
  - context_recall:     Are all relevant chunks retrieved?

Usage:
  python -m eval.ragas_eval --tenant <slug> [--queries eval/test_queries.json]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


def run_eval(tenant_slug: str, queries_path: str) -> dict:
    """Run RAGAS evaluation and return a results dict."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

    from retrieval.hybrid import HybridRetriever
    from generation.prompt import build_prompt
    from generation.llm import generate, is_available

    # Load test queries
    queries_file = Path(queries_path)
    if not queries_file.exists():
        raise FileNotFoundError(f"Test queries file not found: {queries_file}")

    test_queries = json.loads(queries_file.read_text(encoding="utf-8"))
    logger.info("Loaded %d test queries from %s", len(test_queries), queries_file)

    retriever = HybridRetriever()

    questions = []
    answers = []
    contexts = []
    ground_truths = []

    for i, item in enumerate(test_queries):
        question = item["question"]
        ground_truth = item["ground_truth"]

        logger.info("[%d/%d] Evaluating: %s", i + 1, len(test_queries), question[:60])

        # Retrieve
        chunks = retriever.retrieve(question, tenant_slug, final_k=5)
        context_texts = [c["text"] for c in chunks]

        # Generate answer
        if is_available() and chunks:
            prompt = build_prompt(question, chunks)
            answer = generate(prompt)
        elif not chunks:
            answer = "İlgili belge bulunamadı."
            logger.warning("No chunks retrieved for question: %s", question)
        else:
            answer = "LLM modeli mevcut değil."
            logger.warning("LLM not available — using placeholder answer")

        questions.append(question)
        answers.append(answer)
        contexts.append(context_texts)
        ground_truths.append(ground_truth)

        logger.info("Answer: %s...", answer[:80])

    # Build RAGAS dataset
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    logger.info("Running RAGAS evaluation on %d samples…", len(questions))
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    scores = {
        "faithfulness": float(result["faithfulness"]),
        "answer_relevancy": float(result["answer_relevancy"]),
        "context_precision": float(result["context_precision"]),
        "context_recall": float(result["context_recall"]),
        "tenant_slug": tenant_slug,
        "n_queries": len(questions),
        "evaluated_at": datetime.now().isoformat(),
    }
    return scores


def _print_table(scores: dict):
    print("\n" + "=" * 50)
    print("  TurkRAG RAGAS Evaluation Results")
    print("=" * 50)
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    for m in metrics:
        val = scores.get(m, 0)
        bar = "█" * int(val * 20)
        print(f"  {m:<22} {val:.3f}  {bar}")
    print("=" * 50)
    print(f"  Tenant: {scores['tenant_slug']}  |  Queries: {scores['n_queries']}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")

    parser = argparse.ArgumentParser(description="TurkRAG RAGAS Evaluation")
    parser.add_argument("--tenant", required=True, help="Tenant slug to evaluate")
    parser.add_argument("--queries", default="eval/test_queries.json", help="Path to test queries JSON")
    args = parser.parse_args()

    scores = run_eval(args.tenant, args.queries)
    _print_table(scores)

    output_path = Path("eval") / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to: {output_path}")
