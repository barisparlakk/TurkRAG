"""Tests for citation extraction and model-output sanitizing."""

from generation.citations import clean_model_artifact_text, extract_citations, strip_think_tags


def _chunk(i, filename="doc.pdf", text="chunk text"):
    return {"filename": filename, "chunk_index": i, "text": text * 10}


class TestStripThinkTags:
    def test_removes_complete_think_block(self):
        assert strip_think_tags("<think>internal</think>answer") == "answer"

    def test_removes_multiline_think_block(self):
        result = strip_think_tags("<think>\nline1\nline2\n</think>final")
        assert result == "final"

    def test_no_think_block_unchanged(self):
        assert strip_think_tags("plain answer") == "plain answer"

    def test_multiple_think_blocks(self):
        result = strip_think_tags("<think>a</think>mid<think>b</think>end")
        assert "think" not in result
        assert "mid" in result and "end" in result

    def test_empty_string(self):
        assert strip_think_tags("") == ""

    def test_strips_leading_whitespace_after_removal(self):
        result = strip_think_tags("<think>x</think>   answer")
        assert result == "answer"


class TestCleanModelArtifactText:
    def test_removes_residual_reasoning_lines(self):
        raw = (
            "<think>internal</think>\n"
            "Okay, let's see. The user wants two questions.\n"
            "Asıl içerik burada.\n"
        )
        assert clean_model_artifact_text(raw) == "Asıl içerik burada."

    def test_preserves_normal_text(self):
        assert clean_model_artifact_text("Normal yanıt.") == "Normal yanıt."


class TestExtractCitations:
    def test_explicit_kaynak_citation(self):
        chunks = [_chunk(0), _chunk(1), _chunk(2)]
        response = "Cevap burada. [Kaynak 1] ve [Kaynak 3] kullanıldı."
        citations = extract_citations(response, chunks)
        cited_indices = {c["chunk_index"] for c in citations}
        assert 0 in cited_indices   # Kaynak 1 → index 0
        assert 2 in cited_indices   # Kaynak 3 → index 2

    def test_citation_index_1_based(self):
        chunks = [_chunk(0, "a.pdf"), _chunk(1, "b.pdf")]
        response = "[Kaynak 2] kullanıldı."
        citations = extract_citations(response, chunks)
        assert any(c["filename"] == "b.pdf" for c in citations)

    def test_no_citation_falls_back_to_all_chunks(self):
        chunks = [_chunk(0), _chunk(1), _chunk(2)]
        citations = extract_citations("Cevap yok kaynak yok.", chunks)
        assert len(citations) == 3

    def test_out_of_range_citation_ignored(self):
        chunks = [_chunk(0)]
        response = "[Kaynak 99] referans."
        citations = extract_citations(response, chunks)
        # No valid citation → fallback to all
        assert len(citations) == len(chunks)

    def test_empty_chunks_returns_empty(self):
        assert extract_citations("[Kaynak 1] cited.", []) == []

    def test_citation_has_required_keys(self):
        chunks = [_chunk(0, "test.pdf", "some text")]
        citations = extract_citations("[Kaynak 1]", chunks)
        assert citations
        for c in citations:
            assert "filename" in c
            assert "chunk_index" in c
            assert "text_preview" in c

    def test_text_preview_truncated_to_120(self):
        chunks = [_chunk(0, text="X")]
        # chunk text is "X" * 10 repeated = 10 chars, preview should be ≤120
        citations = extract_citations("[Kaynak 1]", chunks)
        assert len(citations[0]["text_preview"]) <= 120

    def test_case_insensitive_kaynak(self):
        chunks = [_chunk(0), _chunk(1)]
        response = "[kaynak 1] alıntı."
        citations = extract_citations(response, chunks)
        cited_indices = {c["chunk_index"] for c in citations}
        assert 0 in cited_indices

    def test_deduplication(self):
        chunks = [_chunk(0), _chunk(1)]
        response = "[Kaynak 1] ve yine [Kaynak 1] tekrar."
        citations = extract_citations(response, chunks)
        chunk0_citations = [c for c in citations if c["chunk_index"] == 0]
        assert len(chunk0_citations) == 1
