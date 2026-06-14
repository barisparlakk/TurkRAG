"""Automated evaluation pipeline for TurkRAG.

Simplified metrics that don't require an external LLM judge:
  - faithfulness: ngram overlap between answer and context
  - answer_relevancy: embedding cosine similarity between query and answer
  - context_precision: embedding similarity between query and retrieved chunks
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://turkrag:turkrag_secret@localhost/turkrag")


@dataclass
class EvalResult:
    tenant_id: str
    num_queries: int
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    avg_score: float


def _ngram_overlap(text_a: str, text_b: str, n: int = 3) -> float:
    """Compute character n-gram overlap ratio between two texts."""
    if not text_a or not text_b:
        return 0.0
    a_lower = text_a.lower()
    b_lower = text_b.lower()
    ngrams_a = {a_lower[i:i+n] for i in range(len(a_lower) - n + 1)}
    ngrams_b = {b_lower[i:i+n] for i in range(len(b_lower) - n + 1)}
    if not ngrams_a:
        return 0.0
    return len(ngrams_a & ngrams_b) / len(ngrams_a)


def _cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def faithfulness_score(answer: str, contexts: list[str]) -> float:
    """N-gram overlap between answer and combined context."""
    combined = " ".join(contexts)
    return _ngram_overlap(answer, combined)


def answer_relevancy_score(query: str, answer: str) -> float:
    """Embedding cosine similarity between query and answer."""
    from ingestion.embedder import embed
    q_vec = embed(query)
    a_vec = embed(answer)
    return _cosine_similarity(q_vec, a_vec)


def context_precision_score(query: str, contexts: list[str]) -> float:
    """Average embedding similarity between query and each retrieved chunk."""
    if not contexts:
        return 0.0
    from ingestion.embedder import embed
    q_vec = embed(query)
    scores = []
    for ctx in contexts:
        c_vec = embed(ctx[:512])
        scores.append(_cosine_similarity(q_vec, c_vec))
    return float(np.mean(scores))


def run_evaluation(tenant_id: str, tenant_slug: str | None = None) -> EvalResult:
    """Run eval on test_queries.json against the RAG pipeline."""
    from generation.citations import strip_think_tags
    from generation.llm import generate, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    if tenant_slug is None:
        from api.db import get_conn
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT slug FROM tenants WHERE id=%s", (tenant_id,))
                row = cur.fetchone()
                tenant_slug = row[0] if row else "demo"
        finally:
            conn.close()

    queries_path = Path("eval/test_queries.json")
    if not queries_path.exists():
        raise FileNotFoundError("eval/test_queries.json not found")

    test_queries = json.loads(queries_path.read_text(encoding="utf-8"))
    retriever = HybridRetriever()

    faith_scores = []
    relevancy_scores = []
    precision_scores = []

    for item in test_queries:
        question = item["question"]

        chunks = retriever.retrieve(question, tenant_slug, final_k=5)
        context_texts = [c["text"] for c in chunks]

        if is_available() and chunks:
            prompt = build_prompt(question, chunks)
            answer = strip_think_tags(generate(prompt))
        else:
            answer = ""

        if answer and context_texts:
            faith_scores.append(faithfulness_score(answer, context_texts))
            relevancy_scores.append(answer_relevancy_score(question, answer))
        if context_texts:
            precision_scores.append(context_precision_score(question, context_texts))

    faith = float(np.mean(faith_scores)) if faith_scores else 0.0
    relevancy = float(np.mean(relevancy_scores)) if relevancy_scores else 0.0
    precision = float(np.mean(precision_scores)) if precision_scores else 0.0
    avg = float(np.mean([faith, relevancy, precision]))

    return EvalResult(
        tenant_id=tenant_id,
        num_queries=len(test_queries),
        faithfulness=round(faith, 4),
        answer_relevancy=round(relevancy, 4),
        context_precision=round(precision, 4),
        avg_score=round(avg, 4),
    )


def save_eval_result(result: EvalResult) -> str:
    """Persist eval result to PostgreSQL. Returns the eval_run UUID."""
    from api.db import get_conn
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            metrics = {
                "faithfulness": result.faithfulness,
                "answer_relevancy": result.answer_relevancy,
                "context_precision": result.context_precision,
            }
            cur.execute(
                """INSERT INTO eval_runs
                      (tenant_id, run_label, config_json, metrics_json, per_query_json, num_queries, avg_score)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    result.tenant_id,
                    "api-auto-eval",
                    json.dumps({"mode": "hybrid+rerank", "source": "api"}),
                    json.dumps(metrics),
                    json.dumps([]),
                    result.num_queries,
                    result.avg_score,
                ),
            )
            return str(cur.fetchone()[0])
    finally:
        conn.close()
