"""Tests for stream_rag_response — all I/O mocked."""

import asyncio
import json
from unittest.mock import patch


class FakeWebSocket:
    """Collects frames sent during streaming."""

    def __init__(self):
        self.sent = []

    async def send_text(self, text: str):
        self.sent.append(json.loads(text))

    def frames(self, frame_type: str | None = None):
        if frame_type is None:
            return self.sent
        return [f for f in self.sent if f.get("type") == frame_type]


_CHUNKS = [
    {"text": "Bu önemli bir belgedir.", "doc_id": "d1", "chunk_index": 0,
     "filename": "belge.txt", "rrf_score": 0.9},
]


def _run(coro):
    return asyncio.run(coro)


class TestStreamerNoChunks:
    def test_sends_error_when_no_chunks(self):
        ws = FakeWebSocket()
        with patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=[]):
            result = _run(_stream(ws))
        assert result is None
        errors = ws.frames("error")
        assert errors, "Expected at least one error frame"

    def test_no_done_frame_when_no_chunks(self):
        ws = FakeWebSocket()
        with patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=[]):
            _run(_stream(ws))
        assert not ws.frames("done")


class TestStreamerLLMUnavailable:
    def test_sends_error_when_llm_missing(self):
        ws = FakeWebSocket()
        with (
            patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=_CHUNKS),
            patch("generation.llm.is_available", return_value=False),
        ):
            result = _run(_stream(ws))
        assert result is None
        assert ws.frames("error")


class TestStreamerSuccess:
    def _run_success(self):
        ws = FakeWebSocket()
        tokens = ["Merhaba", " dünya", "."]

        def fake_generate(prompt):
            yield from tokens

        with (
            patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=_CHUNKS),
            patch("generation.llm.is_available", return_value=True),
            patch("generation.llm.generate_stream", side_effect=fake_generate),
            patch("generation.followups.generate_followups", return_value=[]),
        ):
            result = _run(_stream(ws, session_id="sess-1"))
        return ws, result

    def test_token_frames_sent(self):
        ws, _ = self._run_success()
        token_frames = ws.frames("token")
        assert len(token_frames) == 3
        assert token_frames[0]["content"] == "Merhaba"

    def test_done_frame_sent(self):
        ws, _ = self._run_success()
        done = ws.frames("done")
        assert len(done) == 1
        assert done[0]["session_id"] == "sess-1"

    def test_result_text_correct(self):
        _, result = self._run_success()
        assert result is not None
        assert result["text"] == "Merhaba dünya."

    def test_result_has_query_time(self):
        _, result = self._run_success()
        assert "query_time_ms" in result
        assert isinstance(result["query_time_ms"], int)

    def test_done_frame_has_citations(self):
        ws, _ = self._run_success()
        done = ws.frames("done")[0]
        assert "citations" in done

    def test_no_error_frames_on_success(self):
        ws, _ = self._run_success()
        assert not ws.frames("error")

    def test_attribution_frame_sent_after_done(self):
        ws = FakeWebSocket()

        def fake_generate(prompt):
            yield "Merhaba."

        attr_payload = {
            "sentences": [{"text": "Merhaba.", "sentence_index": 0, "sources": []}],
        }
        with (
            patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=_CHUNKS),
            patch("generation.llm.is_available", return_value=True),
            patch("generation.llm.generate_stream", side_effect=fake_generate),
            patch("generation.attribution.attribute_answer", return_value=attr_payload),
            patch("generation.followups.generate_followups", return_value=[]),
        ):
            result = _run(_stream(ws))

        assert result is not None
        frame_types = [frame["type"] for frame in ws.frames()]
        assert frame_types.index("done") < frame_types.index("attribution")

    def test_attribution_failure_does_not_block_result(self):
        ws = FakeWebSocket()

        def fake_generate(prompt):
            yield "Merhaba."

        with (
            patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=_CHUNKS),
            patch("generation.llm.is_available", return_value=True),
            patch("generation.llm.generate_stream", side_effect=fake_generate),
            patch("generation.attribution.attribute_answer", side_effect=RuntimeError("embed failed")),
            patch("generation.followups.generate_followups", return_value=[]),
        ):
            result = _run(asyncio.wait_for(_stream(ws), timeout=1))

        assert result is not None
        assert ws.frames("done")
        assert not ws.frames("attribution")
        assert not ws.frames("error")


class TestStreamerException:
    def test_sends_error_frame_on_exception(self):
        ws = FakeWebSocket()

        def exploding_generate(prompt):
            raise RuntimeError("GPU OOM")
            yield  # make it a generator

        with (
            patch("retrieval.hybrid.HybridRetriever.retrieve", return_value=_CHUNKS),
            patch("generation.llm.is_available", return_value=True),
            patch("generation.llm.generate_stream", side_effect=exploding_generate),
        ):
            result = _run(_stream(ws))

        assert result is None
        errors = ws.frames("error")
        assert errors
        assert errors[0]["message"] == "Streaming failed"


async def _stream(ws, session_id=None, top_k=3):
    from generation.streamer import stream_rag_response
    with (
        patch("ingestion.embedder.embed") as mock_embed,
    ):
        import numpy as np
        mock_embed.return_value = np.random.rand(1, 768).astype("float32")
        return await stream_rag_response(
            ws, "Test sorgusu", "test-tenant",
            top_k=top_k, session_id=session_id,
        )
