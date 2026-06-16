"""Semantic cache: skip LLM calls for similar queries using Qdrant."""

import json
import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "semantic_cache"
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.92"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))


@dataclass
class CacheHit:
    answer: str
    citations: list
    tenant_id: str
    access_scope: str
    score: float


class SemanticCache:
    """Query cache backed by a dedicated Qdrant collection."""

    def __init__(self):
        self._disabled = False
        try:
            self._ensure_collection()
        except Exception as exc:
            self._disabled = True
            logger.warning("Semantic cache disabled: %s", exc)

    def _get_client(self):
        from qdrant_client import QdrantClient
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        return QdrantClient(url=url)

    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams

        from ingestion.embedder import embedding_dim

        client = self._get_client()
        desired_size = embedding_dim()
        collections = [c.name for c in client.get_collections().collections]
        if CACHE_COLLECTION in collections:
            current_size = self._collection_vector_size(client)
            if current_size == desired_size:
                return
            if current_size is None:
                logger.warning("Semantic cache collection exists but vector size could not be verified")
                return
            logger.warning(
                "Recreating semantic cache collection: vector size %s != %s",
                current_size,
                desired_size,
            )
            client.delete_collection(CACHE_COLLECTION)

        client.create_collection(
            collection_name=CACHE_COLLECTION,
            vectors_config=VectorParams(size=desired_size, distance=Distance.COSINE),
        )
        logger.info("Created semantic cache collection (dim=%d)", desired_size)

    def _collection_vector_size(self, client) -> int | None:
        """Best-effort extraction of the configured Qdrant vector size."""
        try:
            info = client.get_collection(CACHE_COLLECTION)
            vectors = info.config.params.vectors
            if isinstance(vectors, dict):
                first = next(iter(vectors.values()), None)
                return getattr(first, "size", None)
            return getattr(vectors, "size", None)
        except Exception as exc:
            logger.warning("Could not inspect semantic cache collection: %s", exc)
            return None

    @staticmethod
    def _embed_query(query: str) -> list[float]:
        from ingestion.embedder import embed

        vec = embed([query])[0]
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)

    def get(
        self,
        query: str,
        tenant_id: str,
        threshold: float = CACHE_THRESHOLD,
        access_scope: str = "tenant",
    ) -> CacheHit | None:
        """Check cache for similar query. Returns CacheHit or None."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        if self._disabled:
            return None
        try:
            query_vec = self._embed_query(query)
            client = self._get_client()

            results = client.search(
                collection_name=CACHE_COLLECTION,
                query_vector=query_vec,
                query_filter=Filter(must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                    FieldCondition(key="access_scope", match=MatchValue(value=access_scope)),
                ]),
                limit=1,
                score_threshold=threshold,
            )

            if not results:
                return None

            hit = results[0]
            timestamp = hit.payload.get("timestamp", 0)
            if time.time() - timestamp > CACHE_TTL_SECONDS:
                return None

            logger.info("Cache hit (score=%.3f) for query: %s", hit.score, query[:50])
            return CacheHit(
                answer=hit.payload["answer"],
                citations=json.loads(hit.payload.get("citations", "[]")),
                tenant_id=tenant_id,
                access_scope=hit.payload.get("access_scope", "tenant"),
                score=hit.score,
            )
        except Exception as exc:
            logger.warning("Semantic cache lookup failed: %s", exc)
            return None

    def put(self, query: str, answer: str, citations: list, tenant_id: str, access_scope: str = "tenant"):
        """Store query+answer in cache."""
        import uuid

        from qdrant_client.models import PointStruct

        if self._disabled:
            return
        try:
            query_vec = self._embed_query(query)
            client = self._get_client()

            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=query_vec,
                payload={
                    "query": query,
                    "answer": answer,
                    "citations": json.dumps(citations),
                    "tenant_id": tenant_id,
                    "access_scope": access_scope,
                    "timestamp": time.time(),
                },
            )
            client.upsert(collection_name=CACHE_COLLECTION, points=[point])
            logger.info("Cached answer for query: %s", query[:50])
        except Exception as exc:
            logger.warning("Semantic cache write failed: %s", exc)

    def invalidate(self, tenant_id: str):
        """Clear all cache entries for a tenant."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = self._get_client()
        client.delete(
            collection_name=CACHE_COLLECTION,
            points_selector=Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            ]),
        )
        logger.info("Cache invalidated for tenant: %s", tenant_id)


_cache_instance: SemanticCache | None = None


def get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance
