"""Optional cache (report #7): a Customer-360 read cache + an idempotency helper.

Gated + degradation-safe: if `REDIS_URL` is unset (or the redis client can't be built), `get_cache`
returns a `NullCache` whose reads miss and whose writes are no-ops - so Postgres stays the source of
truth and dev/tests run without Redis.
"""
from cache.client import Cache, NullCache, RedisCache, get_cache

__all__ = ["Cache", "NullCache", "RedisCache", "get_cache"]