"""Fixed-window in-memory rate limiter for upload endpoints (single-process)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_lock = threading.Lock()
_windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
_MAX_CLIENTS = 10_000


def _client_key(request: Request) -> str:
    """Return a coarse client key (IP only; no auth layer in this system)."""
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, limit: int, window_seconds: int = 60) -> None:
    """Raise 429 when the client exceeds `limit` calls in the current window."""
    now = int(time.time())
    window_id = now // window_seconds
    key = _client_key(request)

    with _lock:
        if len(_windows) > _MAX_CLIENTS:
            _windows.clear()  # bound memory; worst case resets counters
        count, stored_window = _windows[key]
        count = count + 1 if stored_window == window_id else 1
        _windows[key] = (count, window_id)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"rate limit exceeded: {limit} requests per {window_seconds}s",
        )
