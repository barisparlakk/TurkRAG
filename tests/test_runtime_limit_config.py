"""Regression tests for startup validation of numeric runtime limits."""

import importlib

import pytest

from api.config import positive_float_env


def test_request_body_limit_must_be_positive_integer(monkeypatch):
    import api.middleware as middleware

    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "0")
    with pytest.raises(RuntimeError, match="MAX_REQUEST_BODY_BYTES must be a positive integer"):
        importlib.reload(middleware)

    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "1024")
    reloaded = importlib.reload(middleware)
    assert reloaded.MAX_REQUEST_BODY_BYTES == 1024


def test_websocket_rate_limit_must_be_positive_integer(monkeypatch):
    import api.limits as limits

    monkeypatch.setenv("WS_RATE_LIMIT_PER_MINUTE", "not-a-number")
    with pytest.raises(RuntimeError, match="WS_RATE_LIMIT_PER_MINUTE must be a positive integer"):
        importlib.reload(limits)

    monkeypatch.setenv("WS_RATE_LIMIT_PER_MINUTE", "45")
    reloaded = importlib.reload(limits)
    assert reloaded.WS_RATE_LIMIT_PER_MINUTE == 45


@pytest.mark.parametrize("invalid_value", ["0", "-0.1", "not-a-number"])
def test_positive_float_env_rejects_non_positive_values(monkeypatch, invalid_value):
    monkeypatch.setenv("CACHE_THRESHOLD", invalid_value)

    with pytest.raises(RuntimeError, match="CACHE_THRESHOLD must be a positive number"):
        positive_float_env("CACHE_THRESHOLD", 0.92)


def test_positive_float_env_reads_valid_value(monkeypatch):
    monkeypatch.setenv("CACHE_THRESHOLD", "0.87")

    assert positive_float_env("CACHE_THRESHOLD", 0.92) == 0.87
