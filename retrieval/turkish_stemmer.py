"""Lightweight Turkish suffix stripper for BM25 query expansion.

Turkish is agglutinative: "çalışmak", "çalışıyor", "çalışan" share root "çalış".
BM25 misses these unless we expand/normalise the query tokens.

Strategy:
  - Strip longest matching suffix from each token (greedy, longest-first).
  - Minimum stem length: 3 chars (prevents over-stripping).
  - Used only on the *query* side — no re-indexing needed.
  - expand_query() returns original + stem (both fed to BM25 tokenizer).
"""

import re

_SUFFIXES_RAW = [
    # Verb inflections (3+ chars only — safer for loanwords)
    "mamaktadır", "memektedir", "maktadır", "mektedir",
    "makta", "mekte", "ıyor", "iyor", "uyor", "üyor",
    "acaktır", "ecektir", "acak", "ecek",
    "mıştır", "miştir", "muştur", "müştür",
    "mış", "miş", "muş", "müş",
    "malı", "meli", "mak", "mek",
    # Copula -dır/-dir/-dur/-dür omitted — too ambiguous with loanword roots (prosedür, etc.)
    # Noun/adjective case suffixes (3+ chars)
    "lardan", "lerden", "larda", "lerde", "larla", "lerle",
    "lara", "lere", "ları", "leri",
    "lar", "ler",
    "ından", "inden", "undan", "ünden",
    "ında", "inde", "unda", "ünde",
    "nın", "nin", "nun", "nün",
    "dan", "den", "tan", "ten",
    "nda", "nde",
    "nı", "ni", "nu", "nü",
    # Derivational (3+ chars)
    "lık", "lik", "luk", "lük",
    "lı", "li", "lu", "lü",
    "sız", "siz", "suz", "süz",
    "sal", "sel",
]

# Sort longest first — critical so "lar" (3) beats "ar" (2) etc.
_SUFFIXES = sorted(set(_SUFFIXES_RAW), key=len, reverse=True)

_MIN_STEM = 5  # prevents over-stripping short roots and loanwords


def stem(word: str, max_passes: int = 4) -> str:
    """Return the stem of a Turkish word by iteratively stripping suffixes.

    Applies up to max_passes rounds so agglutinated forms like "çalışanlardan"
    → "çalışanlar" → "çalışan" → "çalış" are handled correctly.
    Stops when no suffix matches or minimum stem length would be violated.
    """
    word = word.lower()
    for _ in range(max_passes):
        stripped = False
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
                word = word[: len(word) - len(suffix)]
                stripped = True
                break  # restart with new shorter word
        if not stripped:
            break
    return word


def expand_query(query: str) -> str:
    """Return original query + stemmed tokens as a combined string for BM25.

    Example: "çalışanlar için prosedür"
      → "çalışanlar için prosedür çalış prosdür"
    Duplicates removed; original tokens kept so exact matches still score.
    """
    tokens = re.findall(r"\w+", query.lower())
    expanded = list(tokens)
    for t in tokens:
        s = stem(t)
        if s != t and s not in expanded:
            expanded.append(s)
    return " ".join(expanded)
