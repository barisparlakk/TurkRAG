"""Faz 6 — Sentence-level source attribution (XAI).

For each sentence in the generated answer, identifies which retrieved chunk(s)
best support it and returns an attribution score. This makes the system
interpretable: users can see exactly where each claim came from.

Approach
--------
1. Split the answer into sentences using the Turkish sentence splitter.
2. For each sentence, compute cosine similarity against every retrieved chunk.
3. Attribute the sentence to the chunk(s) above the ATTRIBUTION_THRESHOLD.
4. Return a structured attribution dict alongside the answer.

The result can be rendered in the UI as inline citations or a source panel.

Usage (standalone test):
  python -m generation.attribution

Programmatic:
  from generation.attribution import attribute_answer
  result = attribute_answer(answer, chunks)
  # result["sentences"] → list of {text, sources: [{filename, chunk_index, score}]}
"""

import logging
import os
import re

import numpy as np

logger = logging.getLogger(__name__)

# Minimum cosine similarity for a chunk to be cited as a source for a sentence.
ATTRIBUTION_THRESHOLD = float(os.getenv("ATTRIBUTION_THRESHOLD", "0.35"))

# Maximum sources to attribute per sentence (keeps the UI clean).
MAX_SOURCES_PER_SENTENCE = int(os.getenv("ATTRIBUTION_MAX_SOURCES", "3"))


def _split_sentences(text: str) -> list[str]:
    """Light sentence splitter for Turkish answer text."""
    # Split on period/!/?/… followed by space + capital, or end of string
    parts = re.split(r'(?<=[.!?…])\s+(?=[A-ZÇĞİÖŞÜa-z\"])', text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences or [text.strip()]


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D arrays."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def attribute_answer(
    answer: str,
    chunks: list[dict],
    threshold: float = ATTRIBUTION_THRESHOLD,
    max_sources: int = MAX_SOURCES_PER_SENTENCE,
) -> dict:
    """Attribute each answer sentence to retrieved source chunks.

    Parameters
    ----------
    answer : str
        The generated answer text.
    chunks : list[dict]
        Retrieved chunks (each must have at least 'text', 'filename',
        'chunk_index'). Pre-computed embeddings can be passed via the
        optional 'embedding' key to avoid re-encoding.
    threshold : float
        Minimum cosine similarity to attribute a source.
    max_sources : int
        Maximum sources per sentence.

    Returns
    -------
    dict with keys:
      answer      : original answer
      sentences   : list of sentence attribution dicts
      cited_docs  : deduplicated list of cited filenames
      has_sources : bool — True if at least one sentence has a source
    """
    if not answer or not chunks:
        return {
            "answer": answer,
            "sentences": [],
            "cited_docs": [],
            "has_sources": False,
        }

    from ingestion.embedder import embed

    sentences = _split_sentences(answer)
    logger.info("Attributing %d answer sentences to %d chunks", len(sentences), len(chunks))

    # Embed chunks (use cached embedding if already present)
    chunk_texts = [c["text"] for c in chunks]
    chunk_embeddings: list[np.ndarray] = []
    needs_embed = []
    for i, c in enumerate(chunks):
        if "embedding" in c and c["embedding"] is not None:
            chunk_embeddings.append(np.array(c["embedding"], dtype=np.float32))
        else:
            needs_embed.append(i)
            chunk_embeddings.append(None)  # placeholder

    if needs_embed:
        texts_to_embed = [chunk_texts[i] for i in needs_embed]
        vecs = embed(texts_to_embed)
        for j, i in enumerate(needs_embed):
            chunk_embeddings[i] = vecs[j]

    # Embed answer sentences
    sent_vecs = embed(sentences)

    attributed_sentences = []
    all_cited = set()

    for sent_idx, (sent, sent_vec) in enumerate(zip(sentences, sent_vecs, strict=False)):
        sims = [
            _cosine_sim(sent_vec, chunk_embeddings[i])
            for i in range(len(chunks))
        ]

        # Gather sources above threshold, sorted by similarity
        sources = []
        for i, sim in enumerate(sims):
            if sim >= threshold:
                c = chunks[i]
                sources.append({
                    "filename": c.get("filename", ""),
                    "doc_id": c.get("doc_id", ""),
                    "chunk_index": c.get("chunk_index", 0),
                    "score": round(sim, 4),
                    "source_snippet": c["text"][:120],
                })
                all_cited.add(c.get("filename", ""))

        sources.sort(key=lambda x: x["score"], reverse=True)
        sources = sources[:max_sources]

        if not sources:
            # Fall back: attribute to the best-scoring chunk even below threshold
            best_i = int(np.argmax(sims))
            best_sim = sims[best_i]
            if best_sim > 0:
                c = chunks[best_i]
                sources = [{
                    "filename": c.get("filename", ""),
                    "doc_id": c.get("doc_id", ""),
                    "chunk_index": c.get("chunk_index", 0),
                    "score": round(best_sim, 4),
                    "source_snippet": c["text"][:120],
                    "low_confidence": True,
                }]

        attributed_sentences.append({
            "text": sent,
            "sentence_index": sent_idx,
            "sources": sources,
        })

    return {
        "answer": answer,
        "sentences": attributed_sentences,
        "cited_docs": sorted(all_cited),
        "has_sources": any(s["sources"] for s in attributed_sentences),
    }


def format_attribution_text(attribution: dict) -> str:
    """Format attribution as readable text with inline citation markers."""
    lines = []
    for sent in attribution["sentences"]:
        sources = [s for s in sent["sources"] if not s.get("low_confidence")]
        if sources:
            refs = ", ".join(
                f"[{s['filename']}#{s['chunk_index']}]" for s in sources
            )
            lines.append(f"{sent['text']} {refs}")
        else:
            lines.append(sent["text"])
    return " ".join(lines)


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Minimal smoke test with dummy chunks
    sample_answer = (
        "Uzaktan çalışma politikası kapsamında haftada üç gün evden çalışılabilir. "
        "Yıllık izin süresi kıdeme göre değişmektedir. "
        "İlk iki yılda 14 iş günü izin hakkı doğmaktadır."
    )
    sample_chunks = [
        {
            "text": "Uzaktan çalışma politikası: çalışanlar haftada en fazla üç gün evden çalışabilir.",
            "filename": "politika.pdf", "doc_id": "doc1", "chunk_index": 0,
        },
        {
            "text": "Yıllık izin süresi kıdeme göre değişmektedir. İlk iki yılda 14 iş günü.",
            "filename": "izin_hakları.pdf", "doc_id": "doc2", "chunk_index": 1,
        },
        {
            "text": "Şirketin genel müdürü Dr. Ahmet Yılmaz'dır.",
            "filename": "organizasyon.pdf", "doc_id": "doc3", "chunk_index": 0,
        },
    ]

    result = attribute_answer(sample_answer, sample_chunks)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nFormatted:")
    print(format_attribution_text(result))
