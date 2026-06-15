"""RRF fusion tests — pure unit tests with mock BM25/dense stores."""

from unittest.mock import patch

import numpy as np

from retrieval.hybrid import RRF_K, HybridRetriever


def _make_hit(doc_id: str, chunk_index: int, text: str = "") -> dict:
    return {"doc_id": doc_id, "chunk_index": chunk_index, "text": text or f"text-{doc_id}-{chunk_index}",
            "filename": f"{doc_id}.txt"}


class TestRRFFusion:
    def setup_method(self):
        self.r = HybridRetriever()

    def _fuse(self, bm25, dense):
        return self.r._rrf_fusion(bm25, dense)

    def test_empty_both_returns_empty(self):
        assert self._fuse([], []) == []

    def test_empty_bm25_uses_dense_only(self):
        dense = [_make_hit("a", 0), _make_hit("b", 1)]
        result = self._fuse([], dense)
        assert len(result) == 2
        ids = [r["doc_id"] for r in result]
        assert "a" in ids and "b" in ids

    def test_empty_dense_uses_bm25_only(self):
        bm25 = [_make_hit("x", 0), _make_hit("y", 1)]
        result = self._fuse(bm25, [])
        assert len(result) == 2

    def test_agreement_boosts_score(self):
        # doc "a" ranks 1st in both lists → should score higher than "b" in one
        bm25 = [_make_hit("a", 0), _make_hit("b", 1)]
        dense = [_make_hit("a", 0), _make_hit("c", 2)]
        result = self._fuse(bm25, dense)
        top = result[0]["doc_id"]
        assert top == "a", f"Expected 'a' at top, got '{top}'"

    def test_rrf_score_formula(self):
        # Single doc rank-0 in both lists → score = 2 / (0 + RRF_K)
        hit = _make_hit("z", 0)
        result = self._fuse([hit], [hit])
        assert len(result) == 1
        expected = 2.0 / RRF_K
        assert abs(result[0]["rrf_score"] - expected) < 1e-9

    def test_rrf_score_rank1(self):
        # Doc at rank 1 in one list → score = 1 / (1 + RRF_K)
        hits_bm25 = [_make_hit("a", 0), _make_hit("b", 1)]
        hits_dense = [_make_hit("c", 2)]
        result = self._fuse(hits_bm25, hits_dense)
        b_entry = next(r for r in result if r["doc_id"] == "b")
        expected = 1.0 / (1 + RRF_K)
        assert abs(b_entry["rrf_score"] - expected) < 1e-9

    def test_deduplication_same_doc_chunk(self):
        hit = _make_hit("dup", 0)
        result = self._fuse([hit, hit], [hit])
        # Key is (doc_id, chunk_index) so should be 1 unique entry
        assert len(result) == 1

    def test_result_sorted_descending(self):
        bm25 = [_make_hit("a", 0), _make_hit("b", 1), _make_hit("c", 2)]
        dense = [_make_hit("b", 1), _make_hit("a", 0), _make_hit("d", 3)]
        result = self._fuse(bm25, dense)
        scores = [r["rrf_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_rrf_score_present_in_result(self):
        result = self._fuse([_make_hit("a", 0)], [_make_hit("b", 1)])
        for r in result:
            assert "rrf_score" in r
            assert r["rrf_score"] > 0

    def test_original_fields_preserved(self):
        hit = _make_hit("x", 5, "some text")
        result = self._fuse([hit], [])
        assert result[0]["text"] == "some text"
        assert result[0]["filename"] == "x.txt"


class TestRerankerFallback:
    """retrieve() falls back to RRF order when reranker is unavailable."""

    def _run_retrieve(self, reranker_side_effect=None):
        chunks = [_make_hit(f"d{i}", i, f"passage {i} text long enough") for i in range(3)]
        fake_vec = np.zeros(768, dtype="float32")

        with (
            patch("retrieval.hybrid.HYDE_ENABLED", False),
            patch("ingestion.embedder.embed", return_value=fake_vec.reshape(1, -1)),
            patch("retrieval.bm25_store.BM25Store.search", return_value=chunks),
            patch("retrieval.vector_store.VectorStore.search", return_value=chunks),
            patch("retrieval.reranker.rerank", side_effect=reranker_side_effect or [0.9, 0.5, 0.1]),
        ):
            return HybridRetriever().retrieve("sorgu", "t", final_k=3)

    def test_returns_results_when_reranker_unavailable(self):
        results = self._run_retrieve(reranker_side_effect=RuntimeError("model missing"))
        assert len(results) == 3

    def test_rerank_score_equals_rrf_score_on_fallback(self):
        results = self._run_retrieve(reranker_side_effect=RuntimeError("model missing"))
        for r in results:
            assert r["rerank_score"] == r["rrf_score"]

    def test_normal_reranking_applies_scores(self):
        results = self._run_retrieve()
        rerank_scores = [r["rerank_score"] for r in results]
        assert rerank_scores == sorted(rerank_scores, reverse=True)


class TestAccessFiltering:
    def test_retrieve_filters_out_inaccessible_documents(self):
        chunks = [
            _make_hit("allowed-doc", 0, "allowed passage"),
            _make_hit("blocked-doc", 1, "blocked passage"),
        ]
        fake_vec = np.zeros(768, dtype="float32")

        with (
            patch("retrieval.hybrid.HYDE_ENABLED", False),
            patch("ingestion.embedder.embed", return_value=fake_vec.reshape(1, -1)),
            patch("retrieval.bm25_store.BM25Store.search", return_value=chunks),
            patch("retrieval.vector_store.VectorStore.search", return_value=chunks),
            patch("retrieval.reranker.rerank", return_value=[0.9]),
        ):
            results = HybridRetriever().retrieve(
                "sorgu",
                "tenant-a",
                final_k=5,
                accessible_doc_ids={"allowed-doc"},
            )

        assert len(results) == 1
        assert results[0]["doc_id"] == "allowed-doc"
