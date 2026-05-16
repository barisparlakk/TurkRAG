"""Sentence embedding model wrapper with singleton caching.

Requires a local SentenceTransformer model at TURKISH_EMBEDDER_PATH
(default: models/turkish-embedder/). Raises RuntimeError on missing path —
never loads from HuggingFace Hub. Embeddings are L2-normalised.
"""

import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_TURKISH_CHECKPOINT = os.getenv("TURKISH_EMBEDDER_PATH", "models/turkish-embedder")

_model_instance = None


def _get_model():
    """Return the singleton embedding model, loading it on first call."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    from sentence_transformers import SentenceTransformer

    turkish_path = Path(_TURKISH_CHECKPOINT)
    if not turkish_path.exists() or not turkish_path.is_dir():
        raise RuntimeError(
            f"Embedding model not found at '{turkish_path}'. "
            "Download and place the model there, or set TURKISH_EMBEDDER_PATH "
            "to point to a local SentenceTransformer directory. "
            "Never load from HuggingFace Hub in production."
        )
    logger.info("Loading Turkish embedder from %s", turkish_path)
    _model_instance = SentenceTransformer(str(turkish_path))

    dim = getattr(_model_instance, "get_embedding_dimension", None) or getattr(_model_instance, "get_sentence_embedding_dimension", None)
    logger.info("Embedding model loaded. Dimension: %d", dim())
    return _model_instance


def embed(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """Batch-encode texts into normalised float32 embeddings.

    Returns shape (N, D) where D is the embedding dimension (768 for mpnet).
    Vectors are L2-normalised so dot product equals cosine similarity.
    """
    if not texts:
        raise ValueError("texts list must not be empty")

    model = _get_model()
    logger.info("Embedding %d texts (batch_size=%d)", len(texts), batch_size)

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,  # unit vectors for cosine similarity
    )

    return embeddings.astype(np.float32)


def embedding_dim() -> int:
    """Return the embedding dimension of the loaded model."""
    m = _get_model()
    fn = getattr(m, "get_embedding_dimension", None) or getattr(m, "get_sentence_embedding_dimension", None)
    return fn()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    test_texts = [
        "Şirketin iade politikası nedir?",
        "Ürünler 30 gün içinde iade edilebilir.",
        "Uzaktan çalışma kuralları nasıl uygulanır?",
    ]
    vecs = embed(test_texts)
    print(f"Shape: {vecs.shape}, dtype: {vecs.dtype}")
    # Cosine similarity between first two (should be higher than first/third)
    sim_12 = float(np.dot(vecs[0], vecs[1]))
    sim_13 = float(np.dot(vecs[0], vecs[2]))
    print(f"Sim(q1, relevant): {sim_12:.4f}")
    print(f"Sim(q1, unrelated): {sim_13:.4f}")
