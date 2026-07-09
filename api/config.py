"""Runtime configuration helpers."""

import os


def positive_int_env(name: str, default: int) -> int:
    """Read a positive integer environment setting with a clear startup error."""
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return value
