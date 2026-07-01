"""Billing adapter implementing BillingPort (scaffold)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.billing import BillingPort
from domain_core.value_objects import IdempotencyKey, Money


class BillingAdapter(BillingPort):
    """Talks to the billing system. Concrete I/O lands in Phases 5/7."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError("wired in Phase 5")

    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        raise NotImplementedError("wired in Phase 7")

    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        raise NotImplementedError("wired in Phase 7")