from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Cache(Protocol):
    enabled: bool

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None: ...
    def delete(self, key: str) -> None: ...
    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool: ...


class NullCache:
    """Disabled cache: every read misses, writes are no-ops, and idempotency never blocks."""

    enabled = False

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool:
        return True  # "newly added" — no dedupe when caching is off (safe default)


class RedisCache:
    """Thin wrapper over a redis client (sync)."""

    enabled = True

    def __init__(self, client) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        return value.decode() if isinstance(value, bytes) else value

    def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        self._client.set(key, value, ex=ttl_seconds)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def add_if_absent(self, key: str, ttl_seconds: int = 300) -> bool:
        return bool(self._client.set(key, "1", nx=True, ex=ttl_seconds))


_cache: Cache | None = None


def get_cache() -> Cache:
    """Return the process cache (Redis if configured, else a NullCache). Memoized."""
    global _cache
    if _cache is not None:
        return _cache
    url = os.getenv("REDIS_URL")
    if not url:
        _cache = NullCache()
        return _cache
    try:
        import redis  # optional dependency

        _cache = RedisCache(redis.from_url(url))
        logger.info("redis cache enabled")
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis unavailable (%s); caching disabled", exc)
        _cache = NullCache()
    return _cache