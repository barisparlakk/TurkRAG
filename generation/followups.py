"""Generate suggested follow-up questions after a RAG answer."""

import logging

logger = logging.getLogger(__name__)


def generate_followups(query: str, answer: str, max_tokens: int = 120) -> list[str]:
    """Return up to 3 short Turkish follow-up questions based on the Q&A pair.

    Uses max_tokens=120 so the call takes ~3-5 s.
    Returns an empty list on any error so the caller degrades gracefully.
    """
    from generation.citations import strip_think_tags
    from generation.llm import generate, is_available

    if not is_available():
        return []

    snippet_q = query[:200].replace("\n", " ")
    snippet_a = answer[:400].replace("\n", " ")

    prompt = (
        "<|im_start|>system\n"
        "Kullanıcının sorusuna verilen yanıta dayanarak, kullanıcının sorabilecegi "
        "3 kısa Türkçe takip sorusu üret. Her soru yeni satırda olsun, numara veya tire ekleme."
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"Soru: {snippet_q}\nYanıt: {snippet_a} /no_think<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    try:
        raw = strip_think_tags(generate(prompt, max_tokens=max_tokens)).strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        # Filter out lines that look like numbering artifacts
        questions = [l.lstrip("0123456789.-) ").strip() for l in lines if len(l) > 10][:3]
        logger.debug("Generated %d follow-up questions", len(questions))
        return questions
    except Exception as exc:
        logger.warning("Follow-up generation failed: %s", exc)
        return []
