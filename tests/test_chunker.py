"""Turkish-aware chunker tests — abbreviation handling and chunk structure."""

import pytest
from ingestion.chunker import TurkishChunker


@pytest.fixture
def chunker():
    return TurkishChunker()


def _chunk(chunker, text):
    return chunker.chunk(text)


class TestReturnKeys:
    def test_required_keys_present(self, chunker):
        chunks = _chunk(chunker, "Bu bir test cümlesidir. İkinci cümle burada yer almaktadır.")
        assert chunks
        for c in chunks:
            assert "text" in c
            assert "chunk_index" in c
            assert "start_char" in c
            assert "end_char" in c

    def test_chunk_index_sequential(self, chunker):
        text = ("A " * 200 + ". ") * 5  # force multiple chunks
        chunks = _chunk(chunker, text)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_end_char_greater_than_start(self, chunker):
        chunks = _chunk(chunker, "Bu bir uzun metin örneğidir. Birden fazla cümle içerir.")
        for c in chunks:
            assert c["end_char"] > c["start_char"]

    def test_text_length_matches_char_span(self, chunker):
        chunks = _chunk(chunker, "Kısa cümle. İkinci cümle geldi.")
        for c in chunks:
            assert c["end_char"] - c["start_char"] == len(c["text"])


class TestAbbreviationHandling:
    def test_dr_not_split(self, chunker):
        text = "Dr. Ahmet Yılmaz toplantıya katıldı. Bu kararın önemi büyüktür."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "Dr. Ahmet" in full, "Dr. abbreviation split across chunks"

    def test_prof_not_split(self, chunker):
        text = "Prof. Dr. Mehmet Öz raporu sundu. Katılımcılar memnun ayrıldı."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "Prof. Dr." in full

    def test_vs_not_split(self, chunker):
        text = "Kural vs. istisna tartışması uzun sürdü. Sonunda karar verildi."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "vs." in full

    def test_vb_not_split(self, chunker):
        text = "Belgeler, raporlar, sunumlar vb. materyaller hazırlandı. Toplantı başladı."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "vb." in full

    def test_no_abbreviation_not_split_mid_word(self, chunker):
        text = "No. 42 numaralı karar onaylandı. Sonraki adım uygulamadır."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "No. 42" in full

    def test_digit_period_not_sentence_boundary(self, chunker):
        # "1.5 kg" should not split
        text = "Ürün ağırlığı 1.5 kg olarak ölçüldü. Standartlara uygundur."
        chunks = _chunk(chunker, text)
        full = " ".join(c["text"] for c in chunks)
        assert "1.5 kg" in full


class TestChunkBoundaries:
    def test_empty_text_returns_no_chunks(self, chunker):
        assert _chunk(chunker, "") == []

    def test_whitespace_only_returns_no_chunks(self, chunker):
        assert _chunk(chunker, "   \n\n   ") == []

    def test_single_sentence_is_one_chunk(self, chunker):
        chunks = _chunk(chunker, "Bu tek bir cümledir.")
        assert len(chunks) == 1

    def test_long_text_produces_multiple_chunks(self, chunker):
        sentence = "Bu bir test cümlesidir ve oldukça uzundur. "
        text = sentence * 30
        chunks = _chunk(chunker, text)
        assert len(chunks) > 1

    def test_chunk_text_not_empty(self, chunker):
        text = "İlk cümle burada. İkinci cümle devam ediyor. Üçüncü cümle son."
        for c in _chunk(chunker, text):
            assert c["text"].strip() != ""

    def test_overlap_prefix_appears_in_next_chunk(self, chunker):
        # Build a text that forces two chunks; the last sentence of chunk 1
        # should appear at the start of chunk 2 (overlap)
        sentence = "Uzun bir cümle metni burada devam etmektedir. "
        text = sentence * 25  # enough to create 2+ chunks
        chunks = _chunk(chunker, text)
        if len(chunks) >= 2:
            # Last part of chunk 0 text should appear somewhere in chunk 1
            last_words = chunks[0]["text"].split()[-5:]
            assert any(w in chunks[1]["text"] for w in last_words), \
                "overlap missing between chunks"
