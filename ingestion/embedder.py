"""Sentence embedding model wrapper with singleton caching.

Production mode:
  Requires a local SentenceTransformer model at TURKISH_EMBEDDER_PATH
  (default: models/turkish-embedder/). Raises RuntimeError on missing path —
  never loads from HuggingFace Hub.

Experiment mode (EMBEDDING_MODEL env var):
  Set EMBEDDING_MODEL to the name of a local model directory under models/
  to swap in a different model for ablation studies without touching production
  indexes. The experiment embedder is cached separately from the production one.

Embeddings are L2-normalised (unit vectors → dot product = cosine similarity).
"""

import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

_TURKISH_CHECKPOINT = os.getenv("TURKISH_EMBEDDER_PATH", "models/turkish-embedder")

# Per-path model cache: maps model_path_str → SentenceTransformer instance
_model_cache: dict[str, object] = {}


def _load_model(model_path: str):
    """Load a SentenceTransformer from a local path, with per-path caching."""
    if model_path in _model_cache:
        return _model_cache[model_path]

    from sentence_transformers import SentenceTransformer

    p = Path(model_path)
    if not p.exists() or not p.is_dir():
        raise RuntimeError(
            f"Embedding model not found at '{p}'. "
            "Download and place the model there, or set TURKISH_EMBEDDER_PATH / "
            "EMBEDDING_MODEL to point to a local SentenceTransformer directory. "
            "Never load from HuggingFace Hub in production."
        )
    logger.info("Loading embedder from %s", p)
    model = SentenceTransformer(str(p))
    _model_cache[model_path] = model

    dim_fn = getattr(model, "get_embedding_dimension", None) or \
             getattr(model, "get_sentence_embedding_dimension", None)
    logger.info("Embedder loaded from '%s'. Dimension: %d", p, dim_fn())
    return model


def _get_model(model_path: str | None = None):
    """Return the embedding model for *model_path* (defaults to production model)."""
    path = model_path or os.getenv("EMBEDDING_MODEL") or _TURKISH_CHECKPOINT
    return _load_model(path)


def list_available_models() -> list[str]:
    """Return names of locally available embedding models under models/."""
    models_dir = Path("models")
    if not models_dir.exists():
        return []
    return [d.name for d in models_dir.iterdir() if d.is_dir()]


def embed(texts: list[str], batch_size: int = 32, model_path: str | None = None) -> np.ndarray:
    """Batch-encode texts into normalised float32 embeddings.

    Returns shape (N, D) where D is the embedding dimension.
    Vectors are L2-normalised so dot product equals cosine similarity.

    model_path: override which local model to use (for experiments).
                When None, respects EMBEDDING_MODEL env var, then falls back
                to TURKISH_EMBEDDER_PATH.
    """
    if not texts:
        raise ValueError("texts list must not be empty")

    model = _get_model(model_path)
    logger.info("Embedding %d texts (batch_size=%d, model=%s)",
                len(texts), batch_size, model_path or os.getenv("EMBEDDING_MODEL") or "default")

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,  # unit vectors for cosine similarity
    )

    return embeddings.astype(np.float32)


def embedding_dim(model_path: str | None = None) -> int:
    """Return the embedding dimension of the loaded model."""
    m = _get_model(model_path)
    fn = getattr(m, "get_embedding_dimension", None) or \
         getattr(m, "get_sentence_embedding_dimension", None)
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
