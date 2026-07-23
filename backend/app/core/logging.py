"""Logging configuration and request logging middleware."""
from __future__ import annotations

import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # configured once (avoids duplicate handlers under test re-imports)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one line per request with a correlation id, method, path, status and duration."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("app.request").info(
            "rid=%s %s %s -> %s %.1fms", request_id, request.method, request.url.path, response.status_code, duration_ms
        )
        response.headers["x-request-id"] = request_id
        return response
