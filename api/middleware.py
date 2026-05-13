"""Request middleware: inject tenant context, CORS, and request logging."""

import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


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


def setup_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production to dashboard origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
