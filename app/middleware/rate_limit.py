"""In-memory rate limiting middleware (M-16, M-20, M-21).

A single-instance sliding-window limiter keyed by client IP address. Limits are
configurable via ``RATE_LIMIT_PER_MINUTE``. Requests to ``/api/*`` exceeding the
window receive ``429 Too Many Requests``.

Behind a reverse proxy set ``TRUST_PROXY_HEADERS=true`` so the client key is
derived from ``X-Forwarded-For`` / ``X-Real-IP`` instead of the proxy address
(M-20). Stale per-IP entries are pruned periodically so the key map does not
grow unbounded (M-21).
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_WINDOW_SECONDS = 60.0
_CLEANUP_INTERVAL_SECONDS = 60.0


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _cleanup(self, now: float) -> None:
        stale: list[str] = []
        for key, window in self._hits.items():
            while window and now - window[0] >= _WINDOW_SECONDS:
                window.popleft()
            if not window:
                stale.append(key)
        for key in stale:
            del self._hits[key]

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup >= _CLEANUP_INTERVAL_SECONDS:
                self._cleanup(now)
                self._last_cleanup = now
            window = self._hits[key]
            while window and now - window[0] >= _WINDOW_SECONDS:
                window.popleft()
            if len(window) >= self.requests_per_minute:
                return False
            window.append(now)
            return True


rate_limiter = SlidingWindowRateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
)


def _trust_proxy_headers() -> bool:
    return os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")


def _client_key(request: Request) -> str:
    if _trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if not rate_limiter.allow(_client_key(request)):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please retry later."},
                )
        return await call_next(request)
