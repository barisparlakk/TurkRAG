"""Cross-encoder re-ranker for final relevance scoring.

Uses ms-marco-MiniLM-L-6-v2 which generalises well to Turkish text.
Only called on the top-10 fused candidates to keep latency low.
"""

import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker_instance = None


def _get_reranker():
    global _reranker_instance
    if _reranker_instance is not None:
        return _reranker_instance

    from sentence_transformers import CrossEncoder
    logger.info("Loading cross-encoder reranker: %s", _MODEL_NAME)
    _reranker_instance = CrossEncoder(_MODEL_NAME, max_length=512)
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
