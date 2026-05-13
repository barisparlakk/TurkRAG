"""Extract which source chunks were actually cited in the LLM response."""

import re
from typing import List, Dict


def strip_think_tags(text: str) -> str:
    """Remove Qwen3's <think>...</think> scratchpad from the response."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def extract_citations(response: str, context_chunks: List[Dict]) -> List[Dict]:
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
        citations.append({
            "filename": chunk.get("filename", "belge"),
            "chunk_index": chunk.get("chunk_index", i),
            "text_preview": chunk.get("text", "")[:120].strip(),
        })

    return citations
