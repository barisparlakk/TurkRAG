"""Turkish prompt templates for the RAG generation step.

Uses Qwen3's ChatML format so the model stops cleanly and doesn't loop.
Append /no_think to suppress the internal chain-of-thought scratchpad.
History turns are injected between the system message and the current user
turn so the model can answer follow-up questions correctly.
"""


SYSTEM_PROMPT_TR = """Sen yardımcı bir yapay zeka asistanısın.
Sadece aşağıdaki bağlam belgelerini kullanarak Türkçe olarak yanıt ver.
Belgede bulunmayan bilgileri kesinlikle uydurma.
Yanıtının sonunda kullandığın kaynakları belirt (örn: [Kaynak 1]).
Eğer soruyu yanıtlayamıyorsan, bunu açıkça söyle."""

# Keep at most this many prior turns in the prompt to avoid context overflow
MAX_HISTORY_TURNS = 4


def build_prompt(
    query: str,
    context_chunks: list[dict],
    history: list[dict] | None = None,
) -> str:
    """Assemble the full ChatML prompt for Qwen3.

    Args:
        query:          Current user question.
        context_chunks: Retrieved RAG chunks (keys: filename, chunk_index, text).
        history:        Prior turns as list of {"role": "user"|"assistant", "content": str}.
                        Only the last MAX_HISTORY_TURNS pairs are included.
    """
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        filename = chunk.get("filename", "belge")
        chunk_idx = chunk.get("chunk_index", i)
        text = chunk.get("text", "")
        context_parts.append(f"[Kaynak {i + 1}: {filename}, bölüm {chunk_idx}]\n{text}")

    context = "\n\n".join(context_parts)

    # Inject the most recent history turns (user + assistant pairs)
    history_block = ""
    if history:
        recent = history[-(MAX_HISTORY_TURNS * 2):]  # each turn = 2 messages
        for turn in recent:
            role = turn["role"]
            history_block += f"<|im_start|>{role}\n{turn['content']}<|im_end|>\n"

    # Qwen3 ChatML format — /no_think disables the internal scratchpad
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT_TR}<|im_end|>\n"
        f"{history_block}"
        f"<|im_start|>user\n"
        f"Bağlam:\n{context}\n\n"
        f"Soru: {query} /no_think<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
