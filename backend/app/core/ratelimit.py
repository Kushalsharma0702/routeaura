"""Sliding-window rate limiter (in-process).

Per-process only: with several workers each has its own counters. Redis-backed
limiting replaces this when the Redis service is wired in (see TECHNICAL_DECISIONS #8).
"""
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    _hits.clear()


def rate_limit(bucket: str, limit: int, window_s: int) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"{bucket}:{ip}"
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise AppError(429, "rate_limited", "Too many requests, try again later")
        q.append(now)

    return dependency
