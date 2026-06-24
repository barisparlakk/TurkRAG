"""Request middleware: inject tenant context, CORS, and request logging."""

import logging
import os
import time

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(55 * 1024 * 1024)))


def _get_cors_origins() -> list[str]:
    """Return configured CORS origins from env, defaulting to '*' for local dev."""
    app_env = os.getenv("APP_ENV", "development").lower()
    raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
    if not raw_origins:
        if app_env == "production":
            raise RuntimeError("CORS_ORIGINS must be set when APP_ENV=production")
        return ["*"]
    if app_env == "production" and raw_origins == "*":
        raise RuntimeError("CORS_ORIGINS='*' is not allowed when APP_ENV=production")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next):
        t_start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "%s %s → %d (%d ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests before body parsing when Content-Length is present."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_BYTES:
                    return Response(
                        "Request body too large",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
            except ValueError:
                return Response("Invalid Content-Length", status_code=status.HTTP_400_BAD_REQUEST)
        return await call_next(request)


def setup_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI app."""
    cors_origins = _get_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS origins configured: %s", cors_origins)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
