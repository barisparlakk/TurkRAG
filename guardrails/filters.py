"""Content filtering: prompt injection detection, PII masking, hallucination scoring."""

import re

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
    r"(?i)forget\s+(everything|all|your)\s+(instructions?|rules?|context)",
    r"(?i)you\s+are\s+now\s+(a|an|my)\s+",
    r"(?i)new\s+instructions?:\s*",
    r"(?i)system\s*prompt\s*[:=]",
    r"(?i)override\s+(the\s+)?(system|safety|rules?)",
    r"(?i)do\s+not\s+follow\s+(the\s+)?(previous|system)\s+(instructions?|prompt)",
    r"(?i)act\s+as\s+(if\s+)?(you\s+are|a)\s+",
    r"(?i)rolep?lay\s+as\s+",
    r"(?i)pretend\s+(you\s+are|to\s+be)\s+",
    r"(?i)önceki\s+(talimatlar[ıi]|kurallar[ıi])\s*(yok\s+say|unut|görmezden\s+gel)",
    r"(?i)sistem\s+promptu(nu)?\s*(göster|yaz|ver)",
    r"(?i)tüm\s+kurallar[ıi]\s*(unut|görmezden\s+gel|yoksay)",
    r"(?i)yeni\s+talimat(lar)?:\s*",
    r"(?i)sen\s+artık\s+bir\s+",
    r"(?i)rolünü\s+değiştir",
    r"(?i)\bDAN\b.*\bjailbreak\b",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]

_compiled_patterns = [re.compile(p) for p in INJECTION_PATTERNS]

TC_KIMLIK_PATTERN = re.compile(r"\b[1-9]\d{10}\b")
PHONE_PATTERN = re.compile(r"\b0?5\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
IBAN_PATTERN = re.compile(r"\bTR\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b", re.IGNORECASE)


def detect_prompt_injection(text: str) -> bool:
    """Return True if text contains likely prompt injection attempts."""
    return any(pattern.search(text) for pattern in _compiled_patterns)


def filter_pii(text: str) -> str:
    """Mask PII in text (TC kimlik, phone, email, IBAN)."""
    text = TC_KIMLIK_PATTERN.sub("[TC KİMLİK GİZLİ]", text)
    text = PHONE_PATTERN.sub("[TELEFON GİZLİ]", text)
    text = EMAIL_PATTERN.sub("[E-POSTA GİZLİ]", text)
    text = IBAN_PATTERN.sub("[IBAN GİZLİ]", text)
    return text


def check_hallucination_risk(answer: str, context_chunks: list[str]) -> float:
    """Score how grounded the answer is in context (0=hallucinated, 1=fully grounded).

    Uses 4-gram overlap between answer and combined context.
    """
    if not answer or not context_chunks:
        return 0.0

    combined_context = " ".join(context_chunks).lower()
    answer_lower = answer.lower()

    n = 4
    answer_ngrams = {answer_lower[i:i+n] for i in range(len(answer_lower) - n + 1)}
    if not answer_ngrams:
        return 0.0

    context_ngrams = {combined_context[i:i+n] for i in range(len(combined_context) - n + 1)}
    overlap = len(answer_ngrams & context_ngrams)
    return overlap / len(answer_ngrams)
