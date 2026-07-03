"""Billing adapter implementing BillingPort (report #3). Mock is deterministic; Live calls the
external billing system. One vendor change has a one-module blast radius (Blueprint ADR 5.4)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.billing import BillingPort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import get_json, post_json


class MockBillingAdapter(BillingPort):
    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        return []

    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        return f"PAY-{key.value[:10].upper()}"

    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        return None


class LiveBillingAdapter(BillingPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        data = await get_json(self._base, f"/invoices/{customer_id}")
        return data.get("invoices", [])

    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/charge", {
            "customer_id": customer_id, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")

    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        await post_json(self._base, "/deferral", {
            "customer_id": customer_id, "days": days, "idempotency_key": key.value,
        })