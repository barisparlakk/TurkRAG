"""Semantic cache: skip LLM calls for similar queries using Qdrant."""

import json
import logging
import os
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

CACHE_COLLECTION = "semantic_cache"
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.92"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))


@dataclass
class CacheHit:
    answer: str
    citations: list
    tenant_id: str
    score: float


class SemanticCache:
    """Query cache backed by a dedicated Qdrant collection."""

    def __init__(self):
        self._ensure_collection()

    def _get_client(self):
        from qdrant_client import QdrantClient
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        return QdrantClient(url=url)

    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams
        client = self._get_client()
        collections = [c.name for c in client.get_collections().collections]
        if CACHE_COLLECTION not in collections:
            client.create_collection(
                collection_name=CACHE_COLLECTION,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            logger.info("Created semantic cache collection")

    def get(self, query: str, tenant_id: str, threshold: float = CACHE_THRESHOLD) -> CacheHit | None:
        """Check cache for similar query. Returns CacheHit or None."""
        from ingestion.embedder import embed
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_vec = embed(query)
        client = self._get_client()

        results = client.search(
            collection_name=CACHE_COLLECTION,
            query_vector=query_vec,
            query_filter=Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
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
            score=hit.score,
        )

    def put(self, query: str, answer: str, citations: list, tenant_id: str):
        """Store query+answer in cache."""
        import uuid

        from ingestion.embedder import embed
        from qdrant_client.models import PointStruct

        query_vec = embed(query)
        client = self._get_client()

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=query_vec,
            payload={
                "query": query,
                "answer": answer,
                "citations": json.dumps(citations),
                "tenant_id": tenant_id,
                "timestamp": time.time(),
            },
        )
        client.upsert(collection_name=CACHE_COLLECTION, points=[point])
        logger.info("Cached answer for query: %s", query[:50])

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
