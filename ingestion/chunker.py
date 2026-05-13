"""Turkish-aware sentence chunker.

Turkish is agglutinative — naive character splitting breaks morphological
context and degrades retrieval quality. This chunker respects sentence
boundaries while handling Turkish-specific abbreviations.
"""

import regex  # supports variable-width lookbehinds (unlike stdlib re)
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Turkish abbreviations that end in a period but do NOT end a sentence
TURKISH_ABBREVS = {
    "Dr", "Prof", "Doç", "Yrd", "Arş", "Öğr", "Gör",
    "vs", "vb", "bkz", "mad", "fık", "No", "no",
    "Mts", "Blv", "Cad", "Sok", "Tel", "Fax", "KDV",
    "TL", "USD", "EUR", "m²", "km", "cm", "mm",
    "Ör", "örn", "adm", "fig", "Vol", "vol", "ed",
}

# Build negative-lookbehind pattern for abbreviations.
# stdlib re requires fixed-width lookbehinds; the third-party `regex` module
# supports variable-width alternation which is what we need here.
_ABBREV_PATTERN = "|".join(regex.escape(a) for a in sorted(TURKISH_ABBREVS, key=len, reverse=True))

# Sentence boundary: period/!/?/… followed by whitespace+capital, but not after abbreviations
_SENTENCE_SPLIT_RE = regex.compile(
    r"(?<!(?:" + _ABBREV_PATTERN + r"))"  # not after abbreviation
    r"(?<!\d)"                              # not after a digit (e.g. "1.5 kg")
    r"[.!?…]+\s+"                          # punctuation + whitespace
    r"(?=[A-ZÇĞİÖŞÜ\"'«\(])",             # followed by capital or opening quote
    regex.UNICODE,
)

_NEWLINE_RE = regex.compile(r"\n{2,}")


class TurkishChunker:
    """Chunk Turkish text into semantically coherent, overlapping segments.

    Strategy:
    1. Split on sentence boundaries using a regex that understands Turkish
       abbreviations so "Dr. Ahmet" is not split mid-sentence.
    2. Merge short sentences (< MIN_SENTENCE_CHARS) with the next sentence
       to avoid micro-chunks that lose context.
    3. Accumulate sentences into chunks not exceeding MAX_CHARS.
    4. Each chunk gets overlap: the last sentence(s) of the previous chunk
       are prepended (up to OVERLAP_CHARS) to preserve cross-boundary context.
    """

    MAX_CHARS = 800
    OVERLAP_CHARS = 150
    MIN_SENTENCE_CHARS = 40

    def chunk(self, text: str) -> List[Dict]:
        """Return a list of chunk dicts with keys: text, index, char_start."""
        # First split on paragraph breaks, then on sentence boundaries within each paragraph
        paragraphs = _NEWLINE_RE.split(text)
        sentences: List[str] = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_sentences = _SENTENCE_SPLIT_RE.split(para)
            sentences.extend([s.strip() for s in para_sentences if s.strip()])

        sentences = self._merge_short(sentences)
        chunks = self._build_chunks(sentences)

        logger.info("Chunked text into %d chunks (%d sentences input)", len(chunks), len(sentences))
        return chunks

    def _merge_short(self, sentences: List[str]) -> List[str]:
        """Merge sentences shorter than MIN_SENTENCE_CHARS with the next one."""
        merged: List[str] = []
        buffer = ""
        for sent in sentences:
            if buffer:
                buffer = buffer + " " + sent
            else:
                buffer = sent

            if len(buffer) >= self.MIN_SENTENCE_CHARS:
                merged.append(buffer)
                buffer = ""
        if buffer:
            if merged:
                merged[-1] = merged[-1] + " " + buffer
            else:
                merged.append(buffer)
        return merged

    def _build_chunks(self, sentences: List[str]) -> List[Dict]:
        """Accumulate sentences into MAX_CHARS chunks with OVERLAP_CHARS overlap."""
        chunks: List[Dict] = []
        current_sentences: List[str] = []
        current_len = 0
        overlap_prefix = ""
        char_start = 0

        for sent in sentences:
            # If adding this sentence would exceed the limit, flush first
            if current_len + len(sent) + 1 > self.MAX_CHARS and current_sentences:
                chunk_text = overlap_prefix + " ".join(current_sentences) if overlap_prefix else " ".join(current_sentences)
                chunks.append({
                    "text": chunk_text.strip(),
                    "index": len(chunks),
                    "char_start": char_start,
                })
                # Build overlap from tail of current chunk
                overlap_prefix = self._build_overlap(current_sentences)
                char_start += current_len
                current_sentences = []
                current_len = 0

            current_sentences.append(sent)
            current_len += len(sent) + 1  # +1 for space

        # Flush remaining
        if current_sentences:
            chunk_text = overlap_prefix + " ".join(current_sentences) if overlap_prefix else " ".join(current_sentences)
            chunks.append({
                "text": chunk_text.strip(),
                "index": len(chunks),
                "char_start": char_start,
            })

        return chunks

    def _build_overlap(self, sentences: List[str]) -> str:
        """Return the tail of sentences up to OVERLAP_CHARS as overlap prefix."""
        overlap_sents: List[str] = []
        total = 0
        for sent in reversed(sentences):
            if total + len(sent) > self.OVERLAP_CHARS:
                break
            overlap_sents.insert(0, sent)
            total += len(sent) + 1
        return (" ".join(overlap_sents) + " ") if overlap_sents else ""


if __name__ == "__main__":
    import sys
    import re  # noqa: F401 — only needed in __main__ block below
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sample = """
    Dr. Ahmet Yılmaz, şirketin genel müdürüdür. Uzaktan çalışma politikası kapsamında,
    çalışanlar haftada en fazla üç gün evden çalışabilir. Bu haktan yararlanmak için
    yönetici onayı gerekmektedir. Vs. bu tür politikalar her yıl güncellenir.

    İzin hakları: Yıllık izin süresi kıdeme göre değişmektedir. İlk iki yılda 14 iş
    günü, sonraki yıllarda 20 iş günü izin hakkı doğmaktadır. Prof. Dr. Mehmet Öz
    tarafından hazırlanan raporda bu detaylar açıklanmıştır.
    """
    if len(sys.argv) > 1:
        from ingestion.parser import parse_document
        sample = parse_document(sys.argv[1])

    chunker = TurkishChunker()
    result = chunker.chunk(sample)
    for c in result:
        print(f"\n--- Chunk {c['index']} (char_start={c['char_start']}) ---")
        print(c["text"])
