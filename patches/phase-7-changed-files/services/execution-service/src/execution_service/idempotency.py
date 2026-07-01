"""Idempotency store: one result per key, so a retried dispatch never double-executes (CDC 4.7).

In-process for now; Phase 7.5/11 swaps it for a Postgres unique-key table behind this API.
"""
from __future__ import annotations


class InMemoryIdempotencyStore:
    """Remembers the response for each idempotency key."""

    def __init__(self) -> None:
        self._results: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        """Return the prior response for ``key`` or None."""
        return self._results.get(key)

    def put(self, key: str, response: dict) -> None:
        """Store the response for ``key`` (first execution only)."""
        self._results[key] = response