"""Offline tests: no-op cache when REDIS_URL is unset."""
from __future__ import annotations

from cache import NullCache, get_cache


def test_defaults_to_nullcache(monkeypatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    import cache.client as m
    m._cache = None
    c = get_cache()
    assert isinstance(c, NullCache)
    assert c.enabled is False


def test_nullcache_semantics() -> None:
    c = NullCache()
    c.set("k", "v")
    assert c.get("k") is None
    assert c.add_if_absent("k") is True  # never blocks when disabled
    c.delete("k")