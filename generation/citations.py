"""Extract which source chunks were actually cited in the LLM response."""

import re


def strip_think_tags(text: str) -> str:
    """Remove Qwen3's <think>...</think> scratchpad from the response."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def extract_citations(response: str, context_chunks: list[dict]) -> list[dict]:
    """Find which context chunks are referenced in the response.

    Heuristic: look for [Kaynak N] patterns in the response text.
    Returns a list of {filename, chunk_index, text_preview} for each cited source.
    """
    cited_indices = set()

    # Match [Kaynak 1], [Kaynak 2], etc. (1-indexed)
    for match in re.finditer(r"\[Kaynak\s+(\d+)\]", response, re.IGNORECASE):
        n = int(match.group(1)) - 1  # convert to 0-indexed
        if 0 <= n < len(context_chunks):
            cited_indices.add(n)

    # If the model didn't use explicit citations, include all chunks
    # (better to over-cite than to show no sources)
    if not cited_indices:
        cited_indices = set(range(len(context_chunks)))

    citations = []
    for i in sorted(cited_indices):
        chunk = context_chunks[i]
        # Normalise rerank_score to 0-1 range for display.
        # cross-encoder ms-marco logits: ~8 = very relevant, ~-8 = irrelevant.
        # sigmoid maps this to a 0-1 probability; multiply by 100 for percent.
        raw_score = chunk.get("rerank_score")
        reranker_used = chunk.get("_reranker_used", False)
        if raw_score is not None and reranker_used:
            import math
            score = 1.0 / (1.0 + math.exp(-raw_score))  # sigmoid of cross-encoder logit
        else:
            score = None  # no cross-encoder → don't show misleading %
        citations.append({
            "filename": chunk.get("filename", "belge"),
            "chunk_index": chunk.get("chunk_index", i),
            "text_preview": chunk.get("text", "")[:120].strip(),
            "score": round(score, 3) if score is not None else None,
        })

    return citations
