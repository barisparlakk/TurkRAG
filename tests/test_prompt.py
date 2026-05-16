"""Tests for ChatML prompt construction."""

import pytest
from generation.prompt import build_prompt, SYSTEM_PROMPT_TR, MAX_HISTORY_TURNS


def _chunk(i, filename="belge.pdf", text="içerik metni burada yer almaktadır"):
    return {"filename": filename, "chunk_index": i, "text": text}


def _history(n_turns):
    turns = []
    for i in range(n_turns):
        turns.append({"role": "user", "content": f"soru {i}"})
        turns.append({"role": "assistant", "content": f"cevap {i}"})
    return turns


class TestBuildPrompt:
    def test_contains_system_prompt(self):
        prompt = build_prompt("soru", [_chunk(0)])
        assert SYSTEM_PROMPT_TR in prompt

    def test_contains_query(self):
        prompt = build_prompt("test sorusu", [_chunk(0)])
        assert "test sorusu" in prompt

    def test_contains_chunk_text(self):
        prompt = build_prompt("soru", [_chunk(0, text="özel içerik")])
        assert "özel içerik" in prompt

    def test_context_numbered_from_one(self):
        prompt = build_prompt("soru", [_chunk(0), _chunk(1)])
        assert "[Kaynak 1:" in prompt
        assert "[Kaynak 2:" in prompt

    def test_no_think_appended(self):
        prompt = build_prompt("soru", [_chunk(0)])
        assert "/no_think" in prompt

    def test_chatml_structure(self):
        prompt = build_prompt("soru", [_chunk(0)])
        assert "<|im_start|>system" in prompt
        assert "<|im_start|>user" in prompt
        assert "<|im_start|>assistant" in prompt
        assert "<|im_end|>" in prompt

    def test_no_history_no_extra_turns(self):
        prompt = build_prompt("soru", [_chunk(0)], history=None)
        # Only system + user + assistant start → 3 im_start tags
        assert prompt.count("<|im_start|>") == 3

    def test_history_injected(self):
        history = _history(1)  # 1 turn = user + assistant
        prompt = build_prompt("soru", [_chunk(0)], history=history)
        assert "soru 0" in prompt
        assert "cevap 0" in prompt

    def test_history_capped_at_max_turns(self):
        history = _history(MAX_HISTORY_TURNS + 3)  # excess turns
        prompt = build_prompt("soru", [_chunk(0)], history=history)
        # Most recent MAX_HISTORY_TURNS pairs should be present
        last_turn = MAX_HISTORY_TURNS + 2
        assert f"soru {last_turn}" in prompt
        # Very old turns should be dropped
        assert "soru 0" not in prompt

    def test_empty_history_list(self):
        prompt = build_prompt("soru", [_chunk(0)], history=[])
        assert prompt.count("<|im_start|>") == 3

    def test_multiple_chunks_all_in_context(self):
        chunks = [_chunk(i, text=f"metin {i}") for i in range(5)]
        prompt = build_prompt("soru", chunks)
        for i in range(5):
            assert f"metin {i}" in prompt

    def test_filename_in_context(self):
        prompt = build_prompt("soru", [_chunk(0, filename="rapor.pdf")])
        assert "rapor.pdf" in prompt
