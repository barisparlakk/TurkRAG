"""Cross-encoder re-ranker for final relevance scoring.

Uses ms-marco-MiniLM-L-6-v2 which generalises well to Turkish text.
Only called on the top-10 fused candidates to keep latency low.

Set RERANKER_MODEL_PATH to a local SentenceTransformer directory.
Default: models/cross-encoder/
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_reranker_instance = None


def _get_reranker():
    global _reranker_instance
    if _reranker_instance is not None:
        return _reranker_instance

    model_path = Path(os.getenv("RERANKER_MODEL_PATH", "models/cross-encoder"))
    if not model_path.exists() or not model_path.is_dir():
        raise RuntimeError(
            f"Reranker model not found at '{model_path}'. "
            "Download cross-encoder/ms-marco-MiniLM-L-6-v2 and place it there, "
            "or set RERANKER_MODEL_PATH to a local SentenceTransformer directory. "
            "Never load from HuggingFace Hub in production."
        )

    from sentence_transformers import CrossEncoder
    logger.info("Loading cross-encoder reranker from %s", model_path)
    _reranker_instance = CrossEncoder(str(model_path), max_length=512)
    logger.info("Reranker loaded.")
    return _reranker_instance


def rerank(query: str, passages: list[str]) -> list[float]:
    """Score (query, passage) pairs and return a float relevance score per passage.

    Scores are logits (not probabilities) — higher means more relevant.
    Only call this on a small candidate set (≤ 10) due to latency.
    """
    if not passages:
        return []

    model = _get_reranker()
    pairs = [(query, p) for p in passages]
    scores = model.predict(pairs, show_progress_bar=False)

    logger.debug("Reranker scored %d passages", len(scores))
    return [float(s) for s in scores]
