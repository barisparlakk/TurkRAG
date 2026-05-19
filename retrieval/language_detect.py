"""Simple language detection and multi-language stemming support."""

import re

TURKISH_CHARS = set("şğıöüçŞĞİÖÜÇ")
TURKISH_STOPWORDS = {
    "bir", "bu", "ve", "de", "da", "ile", "için", "ne", "var", "olan",
    "gibi", "daha", "çok", "her", "en", "ama", "sonra", "kadar", "o",
    "ben", "sen", "biz", "siz", "olarak", "ancak", "hem", "ya", "ki",
}

ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "of", "in", "to", "for",
    "with", "on", "at", "from", "by", "as", "or", "and", "but", "if",
    "not", "no", "this", "that", "it", "its", "they", "their", "them",
}


def detect_language(text: str) -> str:
    """Detect if text is Turkish or English using heuristics.

    Returns "tr" or "en".
    """
    if not text:
        return "tr"

    turkish_char_count = sum(1 for c in text if c in TURKISH_CHARS)
    char_ratio = turkish_char_count / max(len(text), 1)
    if char_ratio > 0.01:
        return "tr"

    words = set(re.findall(r"\b\w+\b", text.lower()))
    tr_matches = len(words & TURKISH_STOPWORDS)
    en_matches = len(words & ENGLISH_STOPWORDS)

    if tr_matches > en_matches:
        return "tr"
    if en_matches > tr_matches:
        return "en"

    return "tr"


def stem_english(word: str) -> str:
    """Simple English suffix stripper (Porter-lite)."""
    w = word.lower()
    suffixes = ["ation", "ness", "ment", "able", "ible", "ful", "less", "ing", "ous", "ive", "ly", "ed", "er", "es", "s"]
    for s in suffixes:
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[:-len(s)]
    return w


def get_stemmer(lang: str):
    """Return appropriate stemmer function for the language."""
    if lang == "tr":
        from retrieval.turkish_stemmer import stem_turkish
        return stem_turkish
    return stem_english
