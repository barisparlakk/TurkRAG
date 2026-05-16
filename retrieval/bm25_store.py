"""BM25 sparse retrieval per tenant, backed by serialised bm25s indexes."""

import logging
import os
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

BM25_INDEX_DIR = Path(os.getenv("BM25_INDEX_DIR", "indexes"))

_TURKISH_STOPWORDS = [
    "bir", "bu", "şu", "o", "da", "de", "ki", "ile", "için",
    "ve", "veya", "ama", "fakat", "çünkü", "gibi", "kadar",
    "daha", "en", "çok", "az", "her", "hiç", "ne", "nasıl",
    "olan", "olarak", "ise", "hem", "ya", "mi", "mı", "mu",
    "mü", "değil", "var", "yok", "ben", "sen", "biz", "siz", "onlar",
]


class BM25Store:
    """Load a tenant's BM25 index from disk and run keyword searches."""

    def __init__(self, tenant_slug: str):
        self.tenant_slug = tenant_slug
        self._data: dict | None = None

    def _load(self):
        if self._data is not None:
            return

        index_path = BM25_INDEX_DIR / f"bm25_{self.tenant_slug}.pkl"
        if not index_path.exists():
            logger.warning("No BM25 index found for tenant '%s' at %s", self.tenant_slug, index_path)
            self._data = {"retriever": None, "texts": [], "payloads": []}
            return

        with open(index_path, "rb") as f:
            self._data = pickle.load(f)
        logger.info("BM25 index loaded for tenant '%s': %d docs", self.tenant_slug, len(self._data["texts"]))

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """Return top_k BM25 hits for query, each with keys: text, score, bm25_rank."""
        import bm25s

        self._load()
        if not self._data or not self._data.get("texts"):
            logger.warning("BM25 index empty for tenant '%s'", self.tenant_slug)
            return []

        retriever = self._data["retriever"]
        payloads = self._data["payloads"]

        tokenized_query = bm25s.tokenize([query], stopwords=_TURKISH_STOPWORDS)
        results, scores = retriever.retrieve(tokenized_query, k=min(top_k, len(payloads)))

        hits = []
        for idx, score in zip(results[0], scores[0], strict=False):
            payload = payloads[int(idx)]
            hits.append({
                **payload,
                "score": float(score),
                "bm25_rank": len(hits),
            })

        logger.debug("BM25 search returned %d hits for query='%s...'", len(hits), query[:40])
        return hits

    def reload(self):
        """Force reload from disk (called after new documents are indexed)."""
        self._data = None
        self._load()
