"""Shared request and WebSocket rate limiting helpers."""

import os
import time
from collections import defaultdict, deque

from fastapi import Request, WebSocket
from slowapi import Limiter
from slowapi.util import get_remote_address


def rate_limit_key(request: Request) -> str:
    """Key by tenant_id from JWT when possible, otherwise by client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from api.auth import decode_token

            claims = decode_token(auth[7:])
            return f"tenant:{claims['tenant_id']}"
        except Exception:
            pass
    return get_remote_address(request)


RATE_LIMIT = os.getenv("RATE_LIMIT", "60/minute")
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "60/minute")
CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "30/minute")
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "10/minute")
EVAL_RATE_LIMIT = os.getenv("EVAL_RATE_LIMIT", "5/minute")

limiter = Limiter(key_func=rate_limit_key, default_limits=[RATE_LIMIT])

_ws_hits: dict[str, deque[float]] = defaultdict(deque)


def websocket_rate_limited(websocket: WebSocket, key: str, limit: int | None = None, window_seconds: int = 60) -> bool:
    """Return True when a WebSocket caller has exceeded the in-memory rate limit."""
    limit = limit or int(os.getenv("WS_RATE_LIMIT_PER_MINUTE", "30"))
    client_host = websocket.client.host if websocket.client else "unknown"
    bucket_key = f"{client_host}:{key or 'anonymous'}"
    now = time.monotonic()
    hits = _ws_hits[bucket_key]
    while hits and now - hits[0] > window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False
