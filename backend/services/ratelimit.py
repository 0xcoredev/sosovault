"""
Simple in-memory rate limiter for FastAPI.

Provides per-IP rate limiting with configurable windows and limits.
No external dependencies — uses a dict with TTL-based expiry.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .logging import get_logger

log = get_logger("ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limiter middleware.

    Args:
        requests_per_minute: Max requests per IP per minute window.
        burst: Max requests in a 1-second burst window.
    """

    def __init__(self, app, requests_per_minute: int = 60, burst: int = 10):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = burst
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._burst: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _prune(self, store: dict[str, list[float]], window_s: float) -> None:
        now = time.time()
        cutoff = now - window_s
        empty_keys = [k for k, v in store.items() if not v or v[-1] < cutoff]
        for k in empty_keys:
            del store[k]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()

        # Burst check (1-second window)
        self._prune(self._burst, 1.0)
        self._burst[ip].append(now)
        if len(self._burst[ip]) > self.burst:
            log.warning("Burst limit exceeded for %s", ip)
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded (burst). Please slow down."},
            )

        # RPM check (60-second window)
        self._prune(self._requests, 60.0)
        self._requests[ip].append(now)
        if len(self._requests[ip]) > self.rpm:
            log.warning("RPM limit exceeded for %s (%d requests)", ip, len(self._requests[ip]))
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Max 60 requests per minute."},
            )

        response = await call_next(request)
        return response
