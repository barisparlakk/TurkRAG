"""Faz 3 — Error analysis: categorize RAG pipeline failures per query.

For each query the pipeline produces an answer. This module classifies
the result into one of five categories:

  correct          — answer matches ground truth and retrieval succeeded
  retrieval_fail   — relevant doc not in top-k retrieved chunks
  wrong_citation   — retrieval OK but answer contradicts ground truth
  hallucination    — answer contains info absent from retrieved context
  no_answer        — system returned empty / fallback string

Classification uses lightweight heuristics (keyword overlap) so it works
without an external judge LLM.  When an LLM is available, an optional
judge prompt improves accuracy.

Usage:
  python -m eval.error_analysis --tenant demo
                                [--queries eval/test_queries.json]
                                [--mode hybrid+rerank]
                                [--output results/error_analysis.json]
                                [--use-llm-judge]
"""

import argparse
import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

FAILURE_LABELS = ("correct", "retrieval_fail", "wrong_citation", "hallucination", "no_answer")

NO_ANSWER_PHRASES = {
    "ilgili belge bulunamadı",
    "llm modeli mevcut değil",
    "bilgi bulunamadı",
    "cevap veremiyorum",
    "yanıt oluşturulamadı",
}


# ── Heuristic classifier ───────────────────────────────────────────────────────

def _token_overlap(a: str, b: str) -> float:
    """Jaccard overlap on lowercase tokens."""
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def _context_covers_answer(answer: str, context_texts: list[str]) -> bool:
    """Check whether key answer tokens appear in at least one context chunk."""
    answer_tokens = set(re.findall(r"\w{4,}", answer.lower()))
    if not answer_tokens:
        return True  # trivially covered
    for ctx in context_texts:
        ctx_tokens = set(re.findall(r"\w{4,}", ctx.lower()))
        if len(answer_tokens & ctx_tokens) / len(answer_tokens) > 0.4:
            return True
    return False


def _classify_heuristic(
    question: str,
    answer: str,
    ground_truth: str,
    relevant_doc: str,
    retrieved_docs: list[str],
    context_texts: list[str],
) -> str:
    # 1. No-answer check
    answer_lower = answer.strip().lower()
    if not answer_lower or any(phrase in answer_lower for phrase in NO_ANSWER_PHRASES):
        return "no_answer"

    # 2. Retrieval fail: the relevant document was never retrieved
    if relevant_doc and relevant_doc not in retrieved_docs:
        return "retrieval_fail"

    # 3. Hallucination: answer mentions content not grounded in retrieved context
    if not _context_covers_answer(answer, context_texts):
        return "hallucination"

    # 4. Wrong citation: retrieval worked but answer diverges from ground truth
    overlap = _token_overlap(answer, ground_truth)
    if overlap < 0.15:
        return "wrong_citation"

    return "correct"


# ── Optional LLM judge ─────────────────────────────────────────────────────────

JUDGE_PROMPT = """\
<|im_start|>system
Sen bir RAG sistem değerlendirme uzmanısın. Sana bir soru, sistem yanıtı ve
referans yanıt verilecek. Aşağıdaki kategorilerden birini seç:
  correct        — yanıt doğru ve eksiksiz
  retrieval_fail — ilgili bilgi hiç getirilmemiş
  wrong_citation — bilgi getirildi ama yanıt referans yanıtla çelişiyor
  hallucination  — yanıt, getirilen belgede olmayan bilgi içeriyor
  no_answer      — sistem yanıt veremedi

Yalnızca kategori adını yaz, başka bir şey ekleme.<|im_end|>
<|im_start|>user
SORU: {question}
REFERANS YANIT: {ground_truth}
SİSTEM YANITI: {answer}
BAĞLAM (ilk 400 kar): {context_snippet}<|im_end|>
<|im_start|>assistant
"""


def _classify_llm(question, answer, ground_truth, context_texts) -> str | None:
    try:
        from generation.citations import strip_think_tags
        from generation.llm import generate, is_available
        if not is_available():
            return None
        ctx_snippet = " | ".join(context_texts)[:400]
        prompt = JUDGE_PROMPT.format(
            question=question,
            ground_truth=ground_truth,
            answer=answer,
            context_snippet=ctx_snippet,
        )
        raw = strip_think_tags(generate(prompt, max_tokens=20)).strip().lower()
        for label in FAILURE_LABELS:
            if label in raw:
                return label
        return None
    except Exception as exc:
        logger.warning("LLM judge failed: %s", exc)
        return None


# ── Main analysis runner ───────────────────────────────────────────────────────

def run_error_analysis(
    tenant_slug: str,
    queries_path: str,
    mode: str = "hybrid+rerank",
    top_k: int = 20,
    final_k: int = 5,
    use_llm_judge: bool = False,
) -> dict:
    from generation.citations import strip_think_tags
    from generation.llm import generate, is_available
    from generation.prompt import build_prompt
    from retrieval.hybrid import HybridRetriever

    queries_file = Path(queries_path)
    if not queries_file.exists():
        raise FileNotFoundError(f"Queries file not found: {queries_file}")

    test_queries = json.loads(queries_file.read_text(encoding="utf-8"))
    logger.info("Loaded %d queries [mode=%s]", len(test_queries), mode)

    retriever = HybridRetriever()
    records: list[dict] = []

    for i, item in enumerate(test_queries):
        question = item["question"]
        ground_truth = item.get("ground_truth", "")
        rel_raw = item.get("relevant_doc", item.get("relevant_docs", ""))
        relevant_doc = rel_raw if isinstance(rel_raw, str) else (rel_raw[0] if rel_raw else "")

        chunks = retriever.retrieve(question, tenant_slug, top_k=top_k, final_k=final_k, mode=mode)
        context_texts = [c.get("text", "") for c in chunks]
        retrieved_docs = [c.get("filename", "") for c in chunks]

        if is_available() and chunks:
            prompt = build_prompt(question, chunks)
            answer = strip_think_tags(generate(prompt)).strip()
        elif not chunks:
            answer = "İlgili belge bulunamadı."
        else:
            answer = "LLM modeli mevcut değil."

        # Classify
        if use_llm_judge:
            label = _classify_llm(question, answer, ground_truth, context_texts)
        else:
            label = None

        if label is None:
            label = _classify_heuristic(
                question, answer, ground_truth, relevant_doc, retrieved_docs, context_texts
            )

        record = {
            "question": question,
            "ground_truth": ground_truth,
            "answer": answer,
            "relevant_doc": relevant_doc,
            "retrieved_docs": retrieved_docs,
            "n_chunks_retrieved": len(chunks),
            "category": label,
            "judge": "llm" if use_llm_judge else "heuristic",
        }
        records.append(record)
        logger.info("[%d/%d] %-16s — %s", i + 1, len(test_queries), label, question[:60])

    counts = Counter(r["category"] for r in records)
    n = len(records)
    summary = {
        "retrieval_mode": mode,
        "tenant_slug": tenant_slug,
        "n_queries": n,
        "evaluated_at": datetime.now().isoformat(),
        "category_counts": dict(counts),
        "category_rates": {k: v / n for k, v in counts.items()} if n else {},
    }

    return {"summary": summary, "per_query": records}


def _print_report(result: dict) -> None:
    s = result["summary"]
    print("\n" + "=" * 50)
    print(f"  Error Analysis  |  mode={s['retrieval_mode']}")
    print("=" * 50)
    for label in FAILURE_LABELS:
        count = s["category_counts"].get(label, 0)
        rate = s["category_rates"].get(label, 0.0)
        bar = "█" * int(rate * 20)
        print(f"  {label:<18} {count:>3}  {rate:.1%}  {bar}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="TurkRAG Error Analysis")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--queries", default="eval/test_queries.json")
    parser.add_argument("--mode", default="hybrid+rerank",
                        choices=["sparse", "dense", "hybrid", "hybrid+rerank"])
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--use-llm-judge", action="store_true",
                        help="Use LLM as judge (slower but more accurate)")
    parser.add_argument("--output", default="results/error_analysis.json")
    args = parser.parse_args()

    result = run_error_analysis(
        tenant_slug=args.tenant,
        queries_path=args.queries,
        mode=args.mode,
        top_k=args.top_k,
        final_k=args.final_k,
        use_llm_judge=args.use_llm_judge,
    )
    _print_report(result)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved: %s", out)


if __name__ == "__main__":
    import sys
    sys.exit(main())
