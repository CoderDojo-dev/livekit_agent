"""Sliding-window throttle."""
from __future__ import annotations

from business_api.infrastructure.auth import rate_limit


def test_allows_up_to_the_limit_then_refuses():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:1", limit=3) for _ in range(3))
    assert rate_limit.check("ip:1", limit=3) is False


def test_buckets_are_independent():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:a", limit=2) for _ in range(2))
    assert rate_limit.check("ip:a", limit=2) is False
    assert rate_limit.check("ip:b", limit=2) is True


def test_reset_clears_a_bucket():
    rate_limit.clear_all()
    assert all(rate_limit.check("ip:c", limit=2) for _ in range(2))
    rate_limit.reset("ip:c")
    assert rate_limit.check("ip:c", limit=2) is True