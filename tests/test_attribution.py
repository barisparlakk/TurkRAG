"""Tests for sentence-level attribution helpers."""

import numpy as np

from generation.attribution import attribute_answer


def test_blank_answer_has_no_attribution():
    result = attribute_answer("   ", [{"text": "Kaynak metin", "filename": "doc.txt"}])

    assert result == {
        "answer": "   ",
        "sentences": [],
        "cited_docs": [],
        "has_sources": False,
    }


def test_low_confidence_fallback_is_reflected_in_cited_docs(monkeypatch):
    def fake_embed(texts):
        vectors = {
            "Yanıt cümlesi.": [1.0, 0.0],
            "Kaynak metin": [0.5, 0.0],
        }
        return np.array([vectors[text] for text in texts], dtype=np.float32)

    monkeypatch.setattr("ingestion.embedder.embed", fake_embed)

    result = attribute_answer(
        "Yanıt cümlesi.",
        [{"text": "Kaynak metin", "filename": "doc.txt", "doc_id": "d1", "chunk_index": 2}],
        threshold=1.1,
    )

    assert result["has_sources"] is True
    assert result["cited_docs"] == ["doc.txt"]
    source = result["sentences"][0]["sources"][0]
    assert source["low_confidence"] is True
    assert source["filename"] == "doc.txt"
