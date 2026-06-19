"""Minimal in-memory rate limiter for the auth endpoints.

Per-IP sliding one-minute window over ``/api/v1/auth/*`` POSTs (login, register,
refresh) — the credential-guessing surface. In-memory by design: perfect for a
single instance; multi-instance deployments should ALSO rate-limit at the
gateway (see docs/DEPLOYMENT.md). Disabled when AUTH_RATE_LIMIT_PER_MINUTE is 0.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.responses import error_response

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque[float]] = {}
_lock = threading.Lock()


def reset() -> None:
    """Clear all counters (used by tests)."""
    with _lock:
        _hits.clear()


def _allow(key: str, limit: int) -> bool:
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > _WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


async def auth_rate_limit_middleware(request: Request, call_next):
    """Reject auth bursts with 429. Reads the limit per request (testable)."""
    limit = settings.AUTH_RATE_LIMIT_PER_MINUTE
    if (
        limit > 0
        and request.method == "POST"
        and request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth/")
    ):
        client_ip = request.client.host if request.client else "unknown"
        if not _allow(client_ip, limit):
            return JSONResponse(
                status_code=429,
                content=error_response(
                    "RATE_LIMITED",
                    "Too many authentication attempts. Try again in a minute.",
                ),
            )
    return await call_next(request)
