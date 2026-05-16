"""Reranker unit tests — CrossEncoder loading and scoring mocked."""

import os
from unittest.mock import MagicMock, patch

import pytest

import retrieval.reranker as reranker_mod

# CrossEncoder is imported locally inside _get_reranker(); patch at source
_CROSS_ENCODER_TARGET = "sentence_transformers.CrossEncoder"


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset cached reranker instance between tests."""
    original = reranker_mod._reranker_instance
    reranker_mod._reranker_instance = None
    yield
    reranker_mod._reranker_instance = original


class TestRerankerLoad:
    def test_missing_path_raises_runtime_error(self, tmp_path):
        missing = tmp_path / "no-model-here"
        with patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(missing)}), pytest.raises(RuntimeError, match="not found"):
            reranker_mod._get_reranker()

    def test_error_message_mentions_path(self, tmp_path):
        missing = tmp_path / "cross-encoder"
        with patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(missing)}), pytest.raises(RuntimeError) as exc_info:
            reranker_mod._get_reranker()
        assert str(missing) in str(exc_info.value)

    def test_singleton_cached_after_load(self, tmp_path):
        model_dir = tmp_path / "cross-encoder"
        model_dir.mkdir()
        mock_model = MagicMock()

        with (
            patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(model_dir)}),
            patch(_CROSS_ENCODER_TARGET, return_value=mock_model) as mock_cls,
        ):
            first = reranker_mod._get_reranker()
            second = reranker_mod._get_reranker()
            assert first is second
            mock_cls.assert_called_once()

    def test_loads_from_env_path(self, tmp_path):
        model_dir = tmp_path / "my-reranker"
        model_dir.mkdir()
        mock_model = MagicMock()

        with (
            patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(model_dir)}),
            patch(_CROSS_ENCODER_TARGET, return_value=mock_model) as mock_cls,
        ):
            reranker_mod._get_reranker()
            mock_cls.assert_called_once_with(str(model_dir), max_length=512)


class TestRerank:
    def _mock_model(self, scores):
        mock = MagicMock()
        mock.predict.return_value = scores
        return mock

    def test_empty_passages_returns_empty(self):
        result = reranker_mod.rerank("query", [])
        assert result == []

    def test_returns_float_per_passage(self, tmp_path):
        model_dir = tmp_path / "cross-encoder"
        model_dir.mkdir()
        mock_model = self._mock_model([1.5, -0.3, 0.7])

        with (
            patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(model_dir)}),
            patch(_CROSS_ENCODER_TARGET, return_value=mock_model),
        ):
            scores = reranker_mod.rerank("hangi belge doğru?", ["metin a", "metin b", "metin c"])

        assert len(scores) == 3
        assert all(isinstance(s, float) for s in scores)
        assert scores == [1.5, -0.3, 0.7]

    def test_scores_match_passage_count(self, tmp_path):
        model_dir = tmp_path / "cross-encoder"
        model_dir.mkdir()
        mock_model = self._mock_model([0.1, 0.9])

        with (
            patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(model_dir)}),
            patch(_CROSS_ENCODER_TARGET, return_value=mock_model),
        ):
            scores = reranker_mod.rerank("sorgu", ["p1", "p2"])

        assert len(scores) == 2

    def test_predict_called_with_pairs(self, tmp_path):
        model_dir = tmp_path / "cross-encoder"
        model_dir.mkdir()
        mock_model = self._mock_model([0.5])

        with (
            patch.dict(os.environ, {"RERANKER_MODEL_PATH": str(model_dir)}),
            patch(_CROSS_ENCODER_TARGET, return_value=mock_model),
        ):
            reranker_mod.rerank("soru", ["cevap"])

        call_args = mock_model.predict.call_args[0][0]
        assert call_args == [("soru", "cevap")]
