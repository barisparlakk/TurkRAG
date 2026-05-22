"""TurkRAG evaluation pipeline — lightweight, no external LLM judge.

Metriklerin hesaplanma yöntemi:
  faithfulness      — Cevap tokenlarının context'te bulunma oranı (token overlap)
  answer_relevancy  — Soru ile cevap arasındaki cosine benzerliği (embedding)
  context_precision — Getirilen chunk'ların relevant_doc ile eşleşme oranı
  context_recall    — Beklenen dokümanın top-K içinde bulunma oranı

Bu yaklaşım RAGAS LLM judge gerektirmez, tamamen local ve hızlıdır (~1-2 dakika).

Usage:
  python -m eval.ragas_eval --tenant <slug> [options]
"""

import argparse
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


# ── Metric implementations ─────────────────────────────────────────────────────

def _tokens(text: str) -> set:
    return set(re.findall(r"\w{3,}", text.lower()))


def compute_faithfulness(answer: str, context_texts: list[str]) -> float:
    """Fraction of answer tokens that appear in at least one context chunk."""
    if not answer or not context_texts:
        return 0.0
    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return 0.0
    context_tokens = set()
    for ctx in context_texts:
        context_tokens |= _tokens(ctx)
    covered = answer_tokens & context_tokens
    return len(covered) / len(answer_tokens)


def compute_answer_relevancy(question: str, answer: str) -> float:
    """Cosine similarity between question and answer embeddings."""
    if not answer or answer.startswith("İlgili belge") or answer.startswith("LLM"):
        return 0.0
    from ingestion.embedder import embed
    vecs = embed([question, answer])
    q_vec, a_vec = vecs[0], vecs[1]
    sim = float(np.dot(q_vec, a_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(a_vec) + 1e-9))
    return max(0.0, sim)


def compute_context_precision(retrieved_docs: list[str], relevant_doc: str) -> float:
    """Precision@K — what fraction of retrieved docs are the expected one."""
    if not retrieved_docs or not relevant_doc:
        return 0.0
    hits = sum(1 for d in retrieved_docs if d == relevant_doc)
    return hits / len(retrieved_docs)


def compute_context_recall(retrieved_docs: list[str], relevant_doc: str) -> float:
    """Binary recall — is the expected doc in the retrieved set?"""
    if not relevant_doc:
        return 0.0
    return 1.0 if relevant_doc in retrieved_docs else 0.0


# ── Main eval runner ───────────────────────────────────────────────────────────

def run_eval(
    tenant_slug: str,
    queries_path: str,
    retrieval_mode: str = "hybrid+rerank",
    top_k: int = 20,
    final_k: int = 5,
    run_label: str = "",
) -> dict:
    """Run evaluation and return a results dict."""
    from generation.llm import generate, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    queries_file = Path(queries_path)
    if not queries_file.exists():
        raise FileNotFoundError(f"Test queries file not found: {queries_file}")

    test_queries = json.loads(queries_file.read_text(encoding="utf-8"))
    logger.info("Loaded %d test queries from %s [mode=%s]", len(test_queries), queries_file, retrieval_mode)

    retriever = HybridRetriever()
    per_query = []

    for i, item in enumerate(test_queries):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        relevant_doc = item.get("relevant_doc", "")
        logger.info("[%d/%d] %s", i + 1, len(test_queries), question[:70])

        chunks = retriever.retrieve(question, tenant_slug, top_k=top_k, final_k=final_k, mode=retrieval_mode)
        context_texts = [c.get("text", "") for c in chunks]
        retrieved_docs = [c.get("filename", "") for c in chunks]

        if is_available() and chunks:
            prompt = build_prompt(question, chunks)
            answer = generate(prompt)
            logger.info("  Answer: %s…", answer[:80])
        elif not chunks:
            answer = "İlgili belge bulunamadı."
            logger.warning("  No chunks retrieved")
        else:
            answer = "LLM modeli mevcut değil."

        per_query.append({
            "question": question,
            "answer": answer,
            "ground_truth": ground_truth,
            "relevant_doc": relevant_doc,
            "retrieved_docs": retrieved_docs,
            "faithfulness":       compute_faithfulness(answer, context_texts),
            "answer_relevancy":   compute_answer_relevancy(question, answer),
            "context_precision":  compute_context_precision(retrieved_docs, relevant_doc),
            "context_recall":     compute_context_recall(retrieved_docs, relevant_doc),
        })

    n = len(per_query)
    scores = {
        "run_id":           str(uuid.uuid4()),
        "run_label":        run_label or retrieval_mode,
        "retrieval_mode":   retrieval_mode,
        "top_k":            top_k,
        "final_k":          final_k,
        "tenant_slug":      tenant_slug,
        "n_queries":        n,
        "evaluated_at":     datetime.now().isoformat(),
        "faithfulness":       sum(q["faithfulness"]      for q in per_query) / n if n else 0.0,
        "answer_relevancy":   sum(q["answer_relevancy"]  for q in per_query) / n if n else 0.0,
        "context_precision":  sum(q["context_precision"] for q in per_query) / n if n else 0.0,
        "context_recall":     sum(q["context_recall"]    for q in per_query) / n if n else 0.0,
        "per_query":          per_query,
    }
    return scores


def save_to_db(scores: dict) -> None:
    """Persist evaluation results to the eval_runs PostgreSQL table."""
    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO eval_runs
                (id, tenant_slug, run_label, config, results, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
        """, (
            scores["run_id"],
            scores["tenant_slug"],
            scores["run_label"],
            json.dumps({k: scores[k] for k in ("retrieval_mode", "top_k", "final_k")}),
            json.dumps({k: scores[k] for k in METRICS}),
        ))
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Results saved to eval_runs (run_id=%s)", scores["run_id"])
    except Exception as exc:
        logger.warning("Could not save to DB: %s", exc)


def _print_table(scores: dict) -> None:
    mode  = scores.get("retrieval_mode", "?")
    label = scores.get("run_label", "")
    print("\n" + "=" * 55)
    print(f"  TurkRAG Evaluation  |  mode={mode}  label={label}")
    print("=" * 55)
    for m in METRICS:
        val = scores.get(m, 0.0)
        bar = "█" * int(val * 20)
        print(f"  {m:<22} {val:.3f}  {bar}")
    print("=" * 55)
    print(f"  Tenant: {scores['tenant_slug']}  |  Queries: {scores['n_queries']}")
    print(f"  top_k={scores['top_k']}  final_k={scores['final_k']}  run_id={scores['run_id'][:8]}…")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")

    parser = argparse.ArgumentParser(description="TurkRAG Evaluation")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--retrieval-mode", default="hybrid+rerank",
                        choices=["sparse", "dense", "hybrid", "hybrid+rerank"])
    parser.add_argument("--run-label", default="")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--output", default="")
    parser.add_argument("--save-db", action="store_true")
    args = parser.parse_args()

    scores = run_eval(
        tenant_slug=args.tenant,
        queries_path=args.queries,
        retrieval_mode=args.retrieval_mode,
        top_k=args.top_k,
        final_k=args.final_k,
        run_label=args.run_label,
    )
    _print_table(scores)

    if args.save_db:
        save_to_db(scores)

    out = Path(args.output) if args.output else \
        Path("eval") / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{args.retrieval_mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Remove per_query from the saved file to keep it clean
    save_scores = {k: v for k, v in scores.items() if k != "per_query"}
    out.write_text(json.dumps(save_scores, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to: {out}")
