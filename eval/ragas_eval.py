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
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
RETRIEVAL_KS = (1, 3, 5)
RETRIEVAL_METRICS = [
    "mean_mrr",
    "mean_ap",
    *(f"recall@{k}" for k in RETRIEVAL_KS),
    *(f"ndcg@{k}" for k in RETRIEVAL_KS),
]
LATENCY_FIELDS = [
    "retrieval_latency_ms",
    "generation_latency_ms",
    "total_latency_ms",
]


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


def _relevant_docs(item: dict) -> set[str]:
    raw = item.get("relevant_docs")
    if raw is None:
        raw = item.get("relevant_doc", "")
    if isinstance(raw, str):
        return {raw} if raw else set()
    return {str(doc) for doc in raw if doc}


def compute_context_precision(retrieved_docs: list[str], relevant_docs: set[str]) -> float:
    """Precision@K — what fraction of retrieved docs are the expected one."""
    if not retrieved_docs or not relevant_docs:
        return 0.0
    hits = sum(1 for doc in retrieved_docs if doc in relevant_docs)
    return hits / len(retrieved_docs)


def compute_context_recall(retrieved_docs: list[str], relevant_docs: set[str]) -> float:
    """Fraction of expected documents represented in the retrieved chunks."""
    if not relevant_docs:
        return 0.0
    return len(set(retrieved_docs) & relevant_docs) / len(relevant_docs)


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
    from eval.retrieval_metrics import (
        average_precision,
        mean_reciprocal_rank,
        ndcg_at_k,
        recall_at_k,
    )
    from generation.citations import clean_model_artifact_text
    from generation.llm import generate, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    if top_k < max(RETRIEVAL_KS):
        raise ValueError(f"top_k must be at least {max(RETRIEVAL_KS)} for Recall@K metrics")
    if final_k < 1 or final_k > top_k:
        raise ValueError("final_k must be between 1 and top_k")

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
        relevant_docs = _relevant_docs(item)
        logger.info("[%d/%d] %s", i + 1, len(test_queries), question[:70])

        query_started_at = time.perf_counter()
        retrieval_started_at = query_started_at
        ranked_chunks = retriever.retrieve(
            question,
            tenant_slug,
            top_k=top_k,
            final_k=max(final_k, max(RETRIEVAL_KS)),
            mode=retrieval_mode,
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_started_at) * 1000
        chunks = ranked_chunks[:final_k]
        context_texts = [c.get("text", "") for c in chunks]
        context_docs = [c.get("filename", "") for c in chunks]
        retrieved_docs = [c.get("filename", "") for c in ranked_chunks]

        generation_latency_ms = 0.0
        if is_available() and chunks:
            prompt = build_prompt(question, chunks)
            generation_started_at = time.perf_counter()
            answer = clean_model_artifact_text(generate(prompt))
            generation_latency_ms = (time.perf_counter() - generation_started_at) * 1000
            logger.info("  Answer: %s…", answer[:80])
        elif not chunks:
            answer = "İlgili belge bulunamadı."
            logger.warning("  No chunks retrieved")
        else:
            answer = "LLM modeli mevcut değil."
        total_latency_ms = (time.perf_counter() - query_started_at) * 1000

        query_result = {
            "question": question,
            "answer": answer,
            "ground_truth": ground_truth,
            "relevant_docs": sorted(relevant_docs),
            "retrieved_docs": retrieved_docs,
            "context_docs": context_docs,
            "retrieval_latency_ms": retrieval_latency_ms,
            "generation_latency_ms": generation_latency_ms,
            "total_latency_ms": total_latency_ms,
            "faithfulness":       compute_faithfulness(answer, context_texts),
            "answer_relevancy":   compute_answer_relevancy(question, answer),
            "context_precision":  compute_context_precision(context_docs, relevant_docs),
            "context_recall":     compute_context_recall(context_docs, relevant_docs),
            "mrr": mean_reciprocal_rank(retrieved_docs, relevant_docs),
            "ap": average_precision(retrieved_docs, relevant_docs),
        }
        for k in RETRIEVAL_KS:
            query_result[f"recall@{k}"] = recall_at_k(retrieved_docs, relevant_docs, k)
            query_result[f"ndcg@{k}"] = ndcg_at_k(retrieved_docs, relevant_docs, k)
        per_query.append(query_result)

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
        "mean_mrr": sum(q["mrr"] for q in per_query) / n if n else 0.0,
        "mean_ap": sum(q["ap"] for q in per_query) / n if n else 0.0,
        "retrieval_latency_ms": sum(q["retrieval_latency_ms"] for q in per_query) / n if n else 0.0,
        "generation_latency_ms": sum(q["generation_latency_ms"] for q in per_query) / n if n else 0.0,
        "total_latency_ms": sum(q["total_latency_ms"] for q in per_query) / n if n else 0.0,
        "per_query":          per_query,
    }
    for k in RETRIEVAL_KS:
        scores[f"recall@{k}"] = sum(q[f"recall@{k}"] for q in per_query) / n if n else 0.0
        scores[f"ndcg@{k}"] = sum(q[f"ndcg@{k}"] for q in per_query) / n if n else 0.0
    return scores


def save_to_db(scores: dict) -> None:
    """Persist evaluation results to the eval_runs PostgreSQL table."""
    conn = None
    cur = None
    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenants WHERE slug=%s", (scores["tenant_slug"],))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Tenant not found: {scores['tenant_slug']}")
        tenant_id = row[0]
        metrics = {k: scores.get(k, 0.0) for k in METRICS + RETRIEVAL_METRICS + LATENCY_FIELDS}
        avg_score = sum(scores[k] for k in METRICS) / len(METRICS)
        cur.execute("""
            INSERT INTO eval_runs
                (id, tenant_id, run_label, config_json, metrics_json, per_query_json,
                 num_queries, avg_score, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
        """, (
            scores["run_id"],
            tenant_id,
            scores["run_label"],
            json.dumps({k: scores[k] for k in ("retrieval_mode", "top_k", "final_k")}),
            json.dumps(metrics),
            json.dumps(scores.get("per_query", [])),
            scores["n_queries"],
            avg_score,
        ))
        conn.commit()
        logger.info("Results saved to eval_runs (run_id=%s)", scores["run_id"])
    except Exception as exc:
        logger.warning("Could not save to DB: %s", exc)
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception as exc:
                logger.warning("Could not close eval cursor: %s", exc)
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:
                logger.warning("Could not close eval connection: %s", exc)


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
    for m in RETRIEVAL_METRICS:
        print(f"  {m:<22} {scores.get(m, 0.0):.3f}")
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
    out.write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Results saved to: {out}")
