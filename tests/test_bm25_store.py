"""BM25Store unit tests — index load, search, empty/missing cases."""

import pickle
from unittest.mock import patch

from retrieval.bm25_store import BM25Store


def _write_index(path, texts, payloads):
    import bm25s
    tokenized = bm25s.tokenize(texts, stopwords=None)
    retriever = bm25s.BM25()
    retriever.index(tokenized)
    with open(path, "wb") as f:
        pickle.dump({"retriever": retriever, "texts": texts, "payloads": payloads}, f)


class TestBM25StoreLoad:
    def test_missing_index_returns_empty_search(self, tmp_path):
        store = BM25Store("no-tenant")
        with patch("retrieval.bm25_store.BM25_INDEX_DIR", tmp_path):
            store._data = None  # force reload
            results = store.search("query", top_k=5)
        assert results == []

    def test_empty_index_returns_empty_search(self, tmp_path):
        store = BM25Store("empty")
        store._data = {"retriever": None, "texts": [], "payloads": []}
        results = store.search("anything", top_k=5)
        assert results == []

    def test_index_loaded_once(self, tmp_path):
        texts = ["first doc", "second doc"]
        payloads = [{"text": t, "doc_id": "d1", "filename": "f.txt", "chunk_index": i} for i, t in enumerate(texts)]
        _write_index(tmp_path / "bm25_cached.pkl", texts, payloads)

        store = BM25Store("cached")
        with patch("retrieval.bm25_store.BM25_INDEX_DIR", tmp_path):
            store.search("first")
            first_data = store._data
            store.search("second")
            # same object — loaded only once
            assert store._data is first_data


class TestBM25StoreSearch:
    def _make_store(self, tmp_path, texts, payloads=None):
        if payloads is None:
            payloads = [{"text": t, "doc_id": "d", "filename": "f.txt", "chunk_index": i, "start_char": 0, "end_char": len(t)}
                        for i, t in enumerate(texts)]
        _write_index(tmp_path / "bm25_test.pkl", texts, payloads)
        store = BM25Store("test")
        with patch("retrieval.bm25_store.BM25_INDEX_DIR", tmp_path):
            store._load()
        return store

    def test_returns_list_of_dicts(self, tmp_path):
        store = self._make_store(tmp_path, ["veri gizlilik politikası", "çalışan haklarının korunması"])
        results = store.search("gizlilik")
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_results_have_required_keys(self, tmp_path):
        store = self._make_store(tmp_path, ["bir metin örneği", "başka bir metin"])
        results = store.search("metin", top_k=2)
        for r in results:
            assert "text" in r
            assert "score" in r
            assert "bm25_rank" in r

    def test_top_k_limits_results(self, tmp_path):
        texts = [f"belge numarası {i}" for i in range(10)]
        store = self._make_store(tmp_path, texts)
        assert len(store.search("belge", top_k=3)) <= 3

    def test_top_k_above_corpus_size(self, tmp_path):
        store = self._make_store(tmp_path, ["tek belge"])
        results = store.search("belge", top_k=100)
        assert len(results) <= 1

    def test_relevant_doc_scores_higher(self, tmp_path):
        texts = ["KVKK kişisel veri işleme", "köpek maması fiyatları"]
        store = self._make_store(tmp_path, texts)
        results = store.search("kişisel veri KVKK", top_k=2)
        assert len(results) >= 1
        top_text = results[0]["text"]
        assert "KVKK" in top_text or "kişisel" in top_text

    def test_bm25_rank_ascending(self, tmp_path):
        texts = ["maaş bordrosu çalışan bilgisi", "şirket politikası yönetim", "ürün stok listesi"]
        store = self._make_store(tmp_path, texts)
        results = store.search("maaş bordrosu", top_k=3)
        ranks = [r["bm25_rank"] for r in results]
        assert ranks == list(range(len(results)))

    def test_reload_clears_cache(self, tmp_path):
        store = BM25Store("reload-test")
        store._data = {"retriever": None, "texts": ["stale"], "payloads": []}
        with patch("retrieval.bm25_store.BM25_INDEX_DIR", tmp_path):
            store.reload()
        # No index file → reloaded as empty
        assert store._data["texts"] == []
