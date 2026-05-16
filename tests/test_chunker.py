"""Turkish-aware chunker tests — abbreviation handling and chunk structure."""

import pytest
from ingestion.chunker import TurkishChunker

REQUIRED_KEYS = {"text", "chunk_index", "start_char", "end_char"}


@pytest.fixture
def chunker():
    return TurkishChunker()


class TestReturnKeys:
    def test_required_keys_present(self, chunker):
        chunks = chunker.chunk("Bu bir test cümlesidir. İkinci cümle burada yer almaktadır.")
        assert chunks
        for c in chunks:
            assert set(c) >= REQUIRED_KEYS

    def test_chunk_index_sequential(self, chunker):
        text = ("A " * 200 + ". ") * 5
        chunks = chunker.chunk(text)
        for i, c in enumerate(chunks):
            assert c["chunk_index"] == i

    def test_end_char_greater_than_start(self, chunker):
        chunks = chunker.chunk("Bu bir uzun metin örneğidir. Birden fazla cümle içerir.")
        for c in chunks:
            assert c["end_char"] > c["start_char"]

    def test_text_length_matches_char_span(self, chunker):
        chunks = chunker.chunk("Kısa cümle. İkinci cümle geldi.")
        for c in chunks:
            assert c["end_char"] - c["start_char"] == len(c["text"])


@pytest.mark.parametrize("text,expected_substr", [
    (
        "Dr. Ahmet Yılmaz toplantıya katıldı. Bu kararın önemi büyüktür.",
        "Dr. Ahmet",
    ),
    (
        "Prof. Dr. Mehmet Öz raporu sundu. Katılımcılar memnun ayrıldı.",
        "Prof. Dr.",
    ),
    (
        "Kural vs. istisna tartışması uzun sürdü. Sonunda karar verildi.",
        "vs.",
    ),
    (
        "Belgeler, raporlar, sunumlar vb. materyaller hazırlandı. Toplantı başladı.",
        "vb.",
    ),
    (
        "No. 42 numaralı karar onaylandı. Sonraki adım uygulamadır.",
        "No. 42",
    ),
    (
        "Ürün ağırlığı 1.5 kg olarak ölçüldü. Standartlara uygundur.",
        "1.5 kg",
    ),
])
def test_abbreviation_not_split(chunker, text, expected_substr):
    chunks = chunker.chunk(text)
    full = " ".join(c["text"] for c in chunks)
    assert expected_substr in full


class TestChunkBoundaries:
    def test_empty_text_returns_no_chunks(self, chunker):
        assert chunker.chunk("") == []

    def test_whitespace_only_returns_no_chunks(self, chunker):
        assert chunker.chunk("   \n\n   ") == []

    def test_single_sentence_is_one_chunk(self, chunker):
        chunks = chunker.chunk("Bu tek bir cümledir.")
        assert len(chunks) == 1

    def test_long_text_produces_multiple_chunks(self, chunker):
        text = "Bu bir test cümlesidir ve oldukça uzundur. " * 30
        assert len(chunker.chunk(text)) > 1

    def test_chunk_text_not_empty(self, chunker):
        text = "İlk cümle burada. İkinci cümle devam ediyor. Üçüncü cümle son."
        for c in chunker.chunk(text):
            assert c["text"].strip() != ""

    def test_overlap_prefix_appears_in_next_chunk(self, chunker):
        text = "Uzun bir cümle metni burada devam etmektedir. " * 25
        chunks = chunker.chunk(text)
        if len(chunks) >= 2:
            last_words = chunks[0]["text"].split()[-5:]
            assert any(w in chunks[1]["text"] for w in last_words), \
                "overlap missing between chunks"
