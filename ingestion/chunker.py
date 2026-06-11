"""Turkish-aware sentence chunker.

Turkish is agglutinative — naive character splitting breaks morphological
context and degrades retrieval quality. This chunker respects sentence
boundaries while handling Turkish-specific abbreviations.
"""

import logging

import regex  # supports variable-width lookbehinds (unlike stdlib re)

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

    def chunk(self, text: str) -> list[dict]:
        """Return a list of chunk dicts with keys: text, chunk_index, start_char, end_char."""
        # First split on paragraph breaks, then on sentence boundaries within each paragraph
        paragraphs = _NEWLINE_RE.split(text)
        sentences: list[str] = []
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

    def _merge_short(self, sentences: list[str]) -> list[str]:
        """Merge sentences shorter than MIN_SENTENCE_CHARS with the next one."""
        merged: list[str] = []
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

    @staticmethod
    def _make_chunk(index: int, sentences: list[str], overlap_prefix: str, char_start: int) -> dict:
        raw = (overlap_prefix + " ".join(sentences)) if overlap_prefix else " ".join(sentences)
        text = raw.strip()
        return {"text": text, "chunk_index": index, "start_char": char_start, "end_char": char_start + len(text)}

    def _build_chunks(self, sentences: list[str]) -> list[dict]:
        """Accumulate sentences into MAX_CHARS chunks with OVERLAP_CHARS overlap."""
        chunks: list[dict] = []
        current_sentences: list[str] = []
        current_len = 0
        overlap_prefix = ""
        char_start = 0

        for sent in sentences:
            if current_len + len(sent) + 1 > self.MAX_CHARS and current_sentences:
                chunks.append(self._make_chunk(len(chunks), current_sentences, overlap_prefix, char_start))
                overlap_prefix = self._build_overlap(current_sentences)
                char_start += current_len
                current_sentences = []
                current_len = 0

            current_sentences.append(sent)
            current_len += len(sent) + 1

        if current_sentences:
            chunks.append(self._make_chunk(len(chunks), current_sentences, overlap_prefix, char_start))

        return chunks

    def _build_overlap(self, sentences: list[str]) -> str:
        """Return the tail of sentences up to OVERLAP_CHARS as overlap prefix."""
        overlap_sents: list[str] = []
        total = 0
        for sent in reversed(sentences):
            if total + len(sent) > self.OVERLAP_CHARS:
                break
            overlap_sents.insert(0, sent)
            total += len(sent) + 1
        return (" ".join(overlap_sents) + " ") if overlap_sents else ""


# ── Alternative chunking strategies ───────────────────────────────────────────

class FixedSizeChunker:
    """Chunk by fixed character count with configurable overlap.

    Faster than sentence-boundary splitting but may cut mid-sentence.
    Useful as an ablation baseline.
    """

    def __init__(self, max_chars: int = 800, overlap_chars: int = 150):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str) -> list[dict]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"text": chunk_text, "chunk_index": idx,
                                "start_char": start, "end_char": end})
                idx += 1
            start = end - self.overlap_chars if end < len(text) else len(text)
        logger.info("FixedSizeChunker: %d chunks (max_chars=%d, overlap=%d)",
                    len(chunks), self.max_chars, self.overlap_chars)
        return chunks


class RecursiveChunker:
    """Hierarchical splitting: paragraph → sentence → fixed-size fallback.

    Tries to keep semantic units intact by progressively using finer
    separators only when a unit exceeds max_chars.
    """

    SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

    def __init__(self, max_chars: int = 800, overlap_chars: int = 150):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str) -> list[dict]:
        raw_chunks = self._split(text.strip(), self.SEPARATORS)
        # Merge small chunks together, add overlap between them
        merged = self._merge_with_overlap(raw_chunks)
        result = []
        pos = 0
        for idx, t in enumerate(merged):
            result.append({"text": t, "chunk_index": idx, "start_char": pos, "end_char": pos + len(t)})
            pos += len(t) - self.overlap_chars
        logger.info("RecursiveChunker: %d chunks (max_chars=%d)", len(result), self.max_chars)
        return result

    def _split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.max_chars or not separators:
            return [text] if text else []
        sep, rest = separators[0], separators[1:]
        parts = text.split(sep) if sep else list(text)
        out = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part) <= self.max_chars:
                out.append(part)
            else:
                out.extend(self._split(part, rest))
        return out

    def _merge_with_overlap(self, parts: list[str]) -> list[str]:
        merged: list[str] = []
        buf = ""
        for part in parts:
            if not buf:
                buf = part
            elif len(buf) + len(part) + 1 <= self.max_chars:
                buf = buf + " " + part
            else:
                merged.append(buf)
                # overlap: keep tail of current buf
                tail = buf[-self.overlap_chars:] if self.overlap_chars else ""
                buf = (tail + " " + part).strip() if tail else part
        if buf:
            merged.append(buf)
        return merged


class ParagraphChunker:
    """Split on paragraph breaks (double newline), merge short paragraphs.

    Best for documents with clear section structure (reports, legal texts).
    Falls back to FixedSizeChunker for overly long paragraphs.
    """

    def __init__(self, max_chars: int = 800, overlap_chars: int = 0, min_chars: int = 100):
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.min_chars = min_chars
        self._fixed = FixedSizeChunker(max_chars, overlap_chars)

    def chunk(self, text: str) -> list[dict]:
        raw_paras = [p.strip() for p in _NEWLINE_RE.split(text) if p.strip()]

        # Merge short consecutive paragraphs
        merged_paras: list[str] = []
        buf = ""
        for para in raw_paras:
            candidate = (buf + "\n\n" + para).strip() if buf else para
            if len(candidate) <= self.max_chars:
                buf = candidate
            else:
                if buf:
                    merged_paras.append(buf)
                buf = para
        if buf:
            merged_paras.append(buf)

        # Split any paragraph still exceeding max_chars
        result = []
        idx = 0
        pos = 0
        for para in merged_paras:
            if len(para) <= self.max_chars:
                result.append({"text": para, "chunk_index": idx,
                                "start_char": pos, "end_char": pos + len(para)})
                idx += 1
                pos += len(para)
            else:
                sub_chunks = self._fixed.chunk(para)
                for sc in sub_chunks:
                    sc["chunk_index"] = idx
                    sc["start_char"] += pos
                    sc["end_char"] += pos
                    result.append(sc)
                    idx += 1
                pos += len(para)

        logger.info("ParagraphChunker: %d chunks from %d paragraphs", len(result), len(merged_paras))
        return result


# ── Factory ────────────────────────────────────────────────────────────────────

CHUNKER_REGISTRY = {
    "turkish": TurkishChunker,
    "fixed": FixedSizeChunker,
    "recursive": RecursiveChunker,
    "paragraph": ParagraphChunker,
}

_TURKISH_ATTR_ALIASES = {
    "max_chars": "MAX_CHARS",
    "overlap_chars": "OVERLAP_CHARS",
    "min_sentence_chars": "MIN_SENTENCE_CHARS",
}


def get_chunker(strategy: str = "turkish", **kwargs):
    """Return a chunker instance by name.

    strategy: one of "turkish" (default), "fixed", "recursive", "paragraph"
    kwargs:   passed to the chunker constructor (e.g. max_chars=600, overlap_chars=100)
    """
    cls = CHUNKER_REGISTRY.get(strategy)
    if cls is None:
        raise ValueError(f"Unknown chunker strategy '{strategy}'. "
                         f"Available: {list(CHUNKER_REGISTRY)}")
    # TurkishChunker uses class-level attrs; pass kwargs as instance overrides when supported
    try:
        return cls(**kwargs) if kwargs else cls()
    except TypeError:
        # TurkishChunker has no __init__ params — apply overrides manually.
        # Accept the script-facing snake_case names so experiments actually
        # modify the chunking behaviour instead of silently using defaults.
        obj = cls()
        for k, v in kwargs.items():
            attr_name = _TURKISH_ATTR_ALIASES.get(k, k)
            if hasattr(obj, attr_name):
                setattr(obj, attr_name, v)
        return obj


if __name__ == "__main__":
    import sys
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

    strategy = sys.argv[2] if len(sys.argv) > 2 else "turkish"
    chunker = get_chunker(strategy)
    result = chunker.chunk(sample)
    for c in result:
        print(f"\n--- Chunk {c['chunk_index']} [{strategy}] "
              f"(start={c['start_char']}, end={c['end_char']}, len={len(c['text'])}) ---")
        print(c["text"])
