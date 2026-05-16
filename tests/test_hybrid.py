"""RRF fusion tests — pure unit tests with mock BM25/dense stores."""

import pytest
from retrieval.hybrid import HybridRetriever, RRF_K


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
