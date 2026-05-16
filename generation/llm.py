"""Qwen3-8B-Instruct GGUF inference via llama-cpp-python.

Fails gracefully with a clear error message if the model file is missing,
so the rest of the API can still serve non-LLM endpoints.
"""

import logging
import os
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

# Try both the official naming and unsloth's naming convention
_default_model = "models/qwen3-8b-instruct-q4_k_m.gguf"
if not Path(_default_model).exists():
    _default_model = "models/Qwen3-8B-Q4_K_M.gguf"
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", _default_model)
N_CTX = int(os.getenv("LLM_N_CTX", "4096"))
N_GPU_LAYERS = int(os.getenv("LLM_N_GPU_LAYERS", "-1"))  # -1 = use all available GPU layers
N_THREADS = int(os.getenv("LLM_N_THREADS", "8"))         # CPU threads for prompt eval
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))      # RAG answers rarely exceed 512 tokens

_llm_instance = None
_load_error: Optional[str] = None


def _get_llm():
    global _llm_instance, _load_error

    if _llm_instance is not None:
        return _llm_instance

    if _load_error is not None:
        raise RuntimeError(_load_error)

    model_path = Path(LLM_MODEL_PATH)
    if not model_path.exists():
        _load_error = (
            f"LLM model file not found at '{model_path}'. "
            "Download it with:\n"
            "  pip install huggingface-hub\n"
            "  huggingface-cli download Qwen/Qwen3-8B-Instruct-GGUF "
            "qwen3-8b-instruct-q4_k_m.gguf --local-dir ./models"
        )
        raise RuntimeError(_load_error)

    try:
        from llama_cpp import Llama
        logger.info("Loading LLM from %s (n_ctx=%d, n_gpu_layers=%d)", model_path, N_CTX, N_GPU_LAYERS)
        _llm_instance = Llama(
            model_path=str(model_path),
            n_ctx=N_CTX,
            n_gpu_layers=N_GPU_LAYERS,
            n_threads=N_THREADS,
            verbose=False,
        )
        logger.info("LLM loaded successfully.")
    except Exception as exc:
        _load_error = f"Failed to load LLM: {exc}"
        raise RuntimeError(_load_error) from exc

    return _llm_instance


def is_available() -> bool:
    """Return True if the LLM model file exists and can be loaded."""
    return Path(LLM_MODEL_PATH).exists()


def generate_stream(prompt: str) -> Generator[str, None, None]:
    """Yield tokens one at a time from the LLM.

    Raises RuntimeError if the model is not available.
    """
    llm = _get_llm()
    logger.info("Generating stream (prompt_len=%d)", len(prompt))

    output = llm(
        prompt,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        stream=True,
        stop=["<|im_end|>", "<|im_start|>", "</s>", "<|endoftext|>"],
    )

    for chunk in output:
        token = chunk["choices"][0]["text"]
        if token:
            yield token


def generate(prompt: str) -> str:
    """Generate a full response synchronously (non-streaming)."""
    return "".join(generate_stream(prompt))


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not is_available():
        print(f"Model not available at: {LLM_MODEL_PATH}")
        print("See README.md for download instructions.")
        sys.exit(1)

    prompt = "Merhaba! Türkçe bir şiir yazar mısın?"
    print("Generating...\n")
    for token in generate_stream(prompt):
        print(token, end="", flush=True)
    print()
