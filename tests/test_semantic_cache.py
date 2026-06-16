"""Regression tests for semantic cache vector handling."""

import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from retrieval.semantic_cache import CACHE_COLLECTION, SemanticCache


class _Client:
    def __init__(self, collection_size=None):
        self.collection_size = collection_size
        self.created = []
        self.deleted = []
        self.search_calls = []
        self.upserts = []

    def get_collections(self):
        collections = []
        if self.collection_size is not None:
            collections.append(SimpleNamespace(name=CACHE_COLLECTION))
        return SimpleNamespace(collections=collections)

    def get_collection(self, name):
        assert name == CACHE_COLLECTION
        vectors = SimpleNamespace(size=self.collection_size)
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=vectors)))

    def create_collection(self, collection_name, vectors_config):
        self.collection_size = vectors_config.size
        self.created.append((collection_name, vectors_config))

    def delete_collection(self, collection_name):
        self.collection_size = None
        self.deleted.append(collection_name)

    def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return [
            SimpleNamespace(
                score=0.97,
                payload={
                    "answer": "cached answer",
                    "citations": "[]",
                    "tenant_id": "tenant-1",
                    "access_scope": "user:u1",
                    "timestamp": time.time(),
                },
            )
        ]

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)


def test_ensure_collection_uses_embedding_dimension():
    client = _Client()
    with (
        patch.object(SemanticCache, "_get_client", return_value=client),
        patch("ingestion.embedder.embedding_dim", return_value=768),
    ):
        SemanticCache()

    assert client.created[0][0] == CACHE_COLLECTION
    assert client.created[0][1].size == 768


def test_wrong_size_collection_is_recreated():
    client = _Client(collection_size=384)
    with (
        patch.object(SemanticCache, "_get_client", return_value=client),
        patch("ingestion.embedder.embedding_dim", return_value=768),
    ):
        SemanticCache()

    assert client.deleted == [CACHE_COLLECTION]
    assert client.created[-1][1].size == 768


def test_get_calls_embed_with_list_and_searches_with_flat_vector():
    client = _Client(collection_size=768)
    cache = SemanticCache.__new__(SemanticCache)
    cache._disabled = False

    with (
        patch.object(SemanticCache, "_get_client", return_value=client),
        patch("ingestion.embedder.embed", return_value=np.array([[0.1, 0.2]], dtype=np.float32)) as embed,
    ):
        hit = cache.get("soru", "tenant-1", access_scope="user:u1")

    embed.assert_called_once_with(["soru"])
    assert hit is not None
    assert hit.answer == "cached answer"
    assert client.search_calls[0]["query_vector"] == [0.10000000149011612, 0.20000000298023224]


def test_put_calls_embed_with_list_and_upserts_flat_vector():
    client = _Client(collection_size=768)
    cache = SemanticCache.__new__(SemanticCache)
    cache._disabled = False

    with (
        patch.object(SemanticCache, "_get_client", return_value=client),
        patch("ingestion.embedder.embed", return_value=np.array([[0.3, 0.4]], dtype=np.float32)) as embed,
    ):
        cache.put("soru", "cevap", [], "tenant-1", access_scope="user:u1")

    embed.assert_called_once_with(["soru"])
    point = client.upserts[0]["points"][0]
    assert point.vector == [0.30000001192092896, 0.4000000059604645]


def test_get_failure_returns_none():
    cache = SemanticCache.__new__(SemanticCache)
    cache._disabled = False

    with patch("ingestion.embedder.embed", side_effect=RuntimeError("embed down")):
        assert cache.get("soru", "tenant-1") is None
