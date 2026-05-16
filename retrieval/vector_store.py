"""Qdrant dense vector retrieval per tenant."""

import logging
import os

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


class VectorStore:
    """Run dense similarity search against a tenant's Qdrant collection."""

    def __init__(self, tenant_slug: str):
        self.tenant_slug = tenant_slug
        self.collection_name = f"tenant_{tenant_slug}"
        self._client = None

    def _get_client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=QDRANT_URL)
        return self._client

    def search(self, query_vector: list[float], top_k: int = 20) -> list[dict]:
        """Return top_k dense hits, each with keys: text, doc_id, chunk_index, filename, score, dense_rank."""
        client = self._get_client()

        try:
            results = client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            logger.error("Qdrant search failed for collection '%s': %s", self.collection_name, exc)
            return []

        hits = []
        for rank, hit in enumerate(results):
            payload = hit.payload or {}
            hits.append({
                "text": payload.get("text", ""),
                "doc_id": payload.get("doc_id", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "filename": payload.get("filename", ""),
                "start_char": payload.get("start_char", 0),
                "end_char": payload.get("end_char", 0),
                "score": float(hit.score),
                "dense_rank": rank,
            })

        logger.debug("Dense search returned %d hits for collection '%s'", len(hits), self.collection_name)
        return hits

    def collection_exists(self) -> bool:
        client = self._get_client()
        existing = [c.name for c in client.get_collections().collections]
        return self.collection_name in existing
