"""Conversation memory summarization for long sessions."""

import logging

logger = logging.getLogger(__name__)

SUMMARIZE_THRESHOLD = 6
KEEP_RECENT = 4


def summarize_history(messages: list[dict]) -> str:
    """Summarize older messages into a concise Turkish paragraph using the LLM."""
    from generation.citations import strip_think_tags
    from generation.llm import generate, is_available

    if not is_available() or not messages:
        return ""

    conversation = "\n".join(
        f"{'Kullanıcı' if m['role'] == 'user' else 'Asistan'}: {m['content']}"
        for m in messages
    )

    prompt = (
        "<|im_start|>system\n"
        "Aşağıdaki konuşmayı 2-3 cümleyle Türkçe özetle. "
        "Sadece önemli bilgileri ve sorulan konuları belirt.<|im_end|>\n"
        f"<|im_start|>user\n{conversation} /no_think<|im_end|>\n"
        "<|im_start|>assistant\n"
    )

    summary = strip_think_tags(generate(prompt, max_tokens=200)).strip()
    return summary


def build_context_with_memory(
    session_messages: list[dict],
    max_context_messages: int = 10,
) -> list[dict]:
    """Compress long conversation history for prompt injection.

    If <= SUMMARIZE_THRESHOLD messages, return as-is.
    Otherwise, summarize older messages and prepend summary + keep recent messages.
    """
    if len(session_messages) <= SUMMARIZE_THRESHOLD:
        return session_messages[-max_context_messages:]

    older = session_messages[:-KEEP_RECENT]
    recent = session_messages[-KEEP_RECENT:]

    summary = summarize_history(older)
    if not summary:
        return session_messages[-max_context_messages:]

    return [{"role": "assistant", "content": f"[Önceki konuşma özeti: {summary}]"}] + recent
