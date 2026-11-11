"""Optional in-memory rate limiting for mutating requests.

Off by default (BLACKBOX_RATE_LIMIT_PER_MINUTE=0), preserving the
trusted-network model. When set, each client IP gets that many
non-GET requests per sliding 60-second window; the 429 response
carries a Retry-After header. Reads are never limited.

In-memory and per-process by design: it protects one instance from a
runaway uploader, not a distributed attacker — pair it with a reverse
proxy for internet exposure (see SECURITY.md).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from blackbox_api.config import get_settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_WINDOW_S = 60.0

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_writes(request: Request) -> None:
    limit = get_settings().rate_limit_per_minute
    if limit <= 0 or request.method in _SAFE_METHODS:
        return
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] > _WINDOW_S:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(_WINDOW_S - (now - hits[0])) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded: {limit} writes per minute",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


def reset_rate_limiter() -> None:
    with _lock:
        _hits.clear()
