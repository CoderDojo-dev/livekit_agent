"""In-process sliding-window throttle for the unauthenticated endpoints.

Why NOT packages/cache: get_cache() returns a NullCache when REDIS_URL is unset OR when redis is
unreachable, and NullCache.add_if_absent() returns True ("no dedupe when caching is off (safe
default)"). That is the right default for an idempotency helper and exactly the wrong one for a
brute-force control - the limiter would vanish silently the moment redis hiccuped. business-api
also has no depends_on: redis, and .env.example points REDIS_URL at localhost, which is not
reachable from inside the container.

Scope of this layer: business-api runs a single uvicorn process (apps/business-api/Dockerfile CMD
has no --workers), so one in-process counter observes every request. If the API is ever scaled to
multiple workers or replicas this layer becomes per-replica. The DURABLE per-account lockout in
auth.portal_accounts.locked_until (portal_auth.authenticate) stays correct in every topology and
is the layer that actually stops a targeted attack. Migration path when scaling: move this
counter behind a Redis INCR with a real depends_on, and keep the account lockout as-is.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

WINDOW_SECONDS = 300.0
MAX_ATTEMPTS = 20
_MAX_TRACKED_KEYS = 4096

_buckets: dict[str, deque[float]] = {}
_lock = threading.Lock()


def max_attempts() -> int:
    """Per-window budget for unauthenticated endpoints. Defaults to 20.

    Overridable for local test environments so endpoints can be exercised
    without tripping the throttle.
    """
    try:
        return max(1, int(os.getenv("PORTAL_RATE_LIMIT_ATTEMPTS", str(MAX_ATTEMPTS))))
    except ValueError:
        return MAX_ATTEMPTS


def _prune(now: float) -> None:
    """Drop exhausted buckets, and the oldest ones if the map ever grows unbounded."""
    stale = [
        key
        for key, hits in _buckets.items()
        if not hits or now - hits[-1] > WINDOW_SECONDS
    ]
    for key in stale:
        _buckets.pop(key, None)
    if len(_buckets) > _MAX_TRACKED_KEYS:
        overflow = len(_buckets) - _MAX_TRACKED_KEYS
        oldest = sorted(_buckets, key=lambda key: _buckets[key][-1])[:overflow]
        for key in oldest:
            _buckets.pop(key, None)


def check(key: str, *, limit: int | None = None, window: float = WINDOW_SECONDS) -> bool:
    """Record one attempt for ``key``. False when the window budget is exhausted."""
    if limit is None:
        limit = max_attempts()
    now = time.monotonic()
    with _lock:
        _prune(now)
        hits = _buckets.setdefault(key, deque())
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def reset(key: str) -> None:
    """Clear a bucket after a successful authentication."""
    with _lock:
        _buckets.pop(key, None)


def clear_all() -> None:
    """Test helper: forget every bucket."""
    with _lock:
        _buckets.clear()