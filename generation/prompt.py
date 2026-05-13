"""Turkish prompt templates for the RAG generation step.

Uses Qwen3's ChatML format so the model stops cleanly and doesn't loop.
Append /no_think to suppress the internal chain-of-thought scratchpad.
"""

from typing import List, Dict

SYSTEM_PROMPT_TR = """Sen yardımcı bir yapay zeka asistanısın.
Sadece aşağıdaki bağlam belgelerini kullanarak Türkçe olarak yanıt ver.
Belgede bulunmayan bilgileri kesinlikle uydurma.
Yanıtının sonunda kullandığın kaynakları belirt (örn: [Kaynak 1]).
Eğer soruyu yanıtlayamıyorsan, bunu açıkça söyle."""


def build_prompt(query: str, context_chunks: List[Dict]) -> str:
    """Assemble the full ChatML prompt for Qwen3.

    Context chunks must have keys: filename, chunk_index, text.
    """
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        filename = chunk.get("filename", "belge")
        chunk_idx = chunk.get("chunk_index", i)
        text = chunk.get("text", "")
        context_parts.append(f"[Kaynak {i + 1}: {filename}, bölüm {chunk_idx}]\n{text}")

    context = "\n\n".join(context_parts)

    # Qwen3 ChatML format — /no_think disables the internal scratchpad
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT_TR}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"Bağlam:\n{context}\n\n"
        f"Soru: {query} /no_think<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
