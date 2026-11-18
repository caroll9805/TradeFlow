"""Small in-process sliding-window rate limiter.

Adequate for a single API instance (hackathon / modular monolith). For multiple replicas,
swap the store for Redis — the interface stays the same."""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def auth_rate_limit(request: Request) -> None:
    s = get_settings()
    if not limiter.check(f"auth:{client_ip(request)}", s.auth_rate_limit, s.auth_rate_window_seconds):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, try again later")


def assistant_rate_limit(request: Request) -> None:
    if not limiter.check(f"ai:{client_ip(request)}", 30, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, try again later")
