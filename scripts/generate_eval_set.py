"""Faz 2.2 — BM25 index'ten chunk okuyarak LLM ile sentetik soru-cevap çifti üret.

Her chunk için 1-2 soru üretilir. Çıktı hem JSON (RAGAS formatında) hem CSV
olarak kaydedilir. Sonuçlar manuel doğrulama için CSV'de işaretlenebilir.

Usage:
  python scripts/generate_eval_set.py --tenant demo
                                       [--questions-per-chunk 2]
                                       [--output eval/eval_set_generated.json]
"""

import argparse
import csv
import json
import logging
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


def load_chunks_from_bm25(tenant_slug: str) -> list[dict]:
    """Read all indexed chunks from the BM25 pickle for a tenant."""
    bm25_path = Path("indexes") / f"bm25_{tenant_slug}.pkl"
    if not bm25_path.exists():
        raise FileNotFoundError(f"BM25 index not found: {bm25_path}")

    with bm25_path.open("rb") as f:
        data = pickle.load(f)

    texts = data["texts"]
    payloads = data["payloads"]
    chunks = []
    for text, payload in zip(texts, payloads):
        chunks.append({
            "text": text,
            "filename": payload.get("filename", ""),
            "doc_id": payload.get("doc_id", ""),
            "chunk_index": payload.get("chunk_index", 0),
        })
    logger.info("Loaded %d chunks from %s", len(chunks), bm25_path)
    return chunks


QUESTION_PROMPT = """\
<|im_start|>system
/no_think
Sana bir metin parçası verilecek. Bu metinden doğrudan cevaplanabilecek {n} adet soru üret.
Sorular Türkçe olmalı. Sadece soruları yaz, numara veya açıklama ekleme.
Her soruyu yeni satırda yaz.<|im_end|>
<|im_start|>user
METİN:
{text}

{n} soru üret:<|im_end|>
<|im_start|>assistant
"""

ANSWER_PROMPT = """\
<|im_start|>system
/no_think
Sana bir metin ve soru verilecek. Metne dayanarak soruyu kısaca yanıtla.
Yalnızca metindeki bilgileri kullan.<|im_end|>
<|im_start|>user
METİN:
{text}

SORU: {question}<|im_end|>
<|im_start|>assistant
"""


def generate_qa_for_chunk(chunk: dict, n: int) -> list[dict]:
    """Call LLM to generate n questions and answers for a chunk."""
    from generation.citations import strip_think_tags
    from generation.llm import generate, is_available

    if not is_available():
        logger.warning("LLM not available — skipping chunk")
        return []

    # Generate questions
    q_prompt = QUESTION_PROMPT.format(text=chunk["text"][:600], n=n)
    raw_questions = strip_think_tags(generate(q_prompt, max_tokens=300)).strip()
    # Filter: only lines that look like real Turkish questions (end with ? or are >20 chars Turkish)
    import re as _re
    questions = []
    for line in raw_questions.splitlines():
        line = line.strip()
        # Skip empty, think tags, English reasoning lines
        if not line:
            continue
        if line.startswith("<") or line.lower().startswith("okay") or line.lower().startswith("let me"):
            continue
        # Remove leading numbers/bullets
        line = _re.sub(r"^[\d]+[.)]\s*", "", line).strip()
        if len(line) >= 10:
            questions.append(line)
    questions = questions[:n]

    pairs = []
    for question in questions:
        a_prompt = ANSWER_PROMPT.format(text=chunk["text"][:600], question=question)
        answer = strip_think_tags(generate(a_prompt, max_tokens=150)).strip()
        if question and answer:
            pairs.append({
                "question": question,
                "ground_truth": answer,
                "relevant_doc": chunk["filename"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "source_text": chunk["text"][:200],
                "verified": False,  # manual review flag
            })

    return pairs


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic eval set")
    parser.add_argument("--tenant", required=True, help="Tenant slug")
    parser.add_argument("--questions-per-chunk", type=int, default=2)
    parser.add_argument("--max-chunks", type=int, default=0, help="Limit chunks (0 = all)")
    parser.add_argument("--output", default="eval/eval_set_generated.json")
    parser.add_argument("--csv-output", default="eval/eval_set_generated.csv")
    args = parser.parse_args()

    chunks = load_chunks_from_bm25(args.tenant)
    if args.max_chunks > 0:
        chunks = chunks[:args.max_chunks]
        logger.info("Limited to %d chunks", len(chunks))

    all_pairs = []
    for i, chunk in enumerate(chunks):
        logger.info("[%d/%d] Generating for: %s (chunk %d)",
                    i + 1, len(chunks), chunk["filename"], chunk["chunk_index"])
        pairs = generate_qa_for_chunk(chunk, args.questions_per_chunk)
        all_pairs.extend(pairs)
        logger.info("  → %d Q-A pairs (total so far: %d)", len(pairs), len(all_pairs))

    # Save RAGAS-compatible JSON
    ragas_format = [{"question": p["question"], "ground_truth": p["ground_truth"],
                     "relevant_doc": p["relevant_doc"]} for p in all_pairs]
    out_json = Path(args.output)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(ragas_format, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("RAGAS JSON: %s (%d pairs)", out_json, len(ragas_format))

    # Save full CSV for manual review
    out_csv = Path(args.csv_output)
    fieldnames = ["question", "ground_truth", "relevant_doc", "doc_id", "chunk_index",
                  "source_text", "verified"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_pairs)
    logger.info("Review CSV: %s", out_csv)
    logger.info("Done. Generated %d Q-A pairs from %d chunks.", len(all_pairs), len(chunks))


if __name__ == "__main__":
    sys.exit(main())
