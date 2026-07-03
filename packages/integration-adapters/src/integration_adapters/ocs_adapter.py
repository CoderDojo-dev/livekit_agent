"""OCS/prepaid balance adapter implementing BalancePort (report #3)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.balance import BalancePort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import get_json, post_json


class MockOcsAdapter(BalancePort):
    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        return {"customer_id": customer_id, "credit": 0.0, "currency": "TND", "data_remaining_mb": 0}

    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        return f"TOP-{key.value[:10].upper()}"

    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        return None


class LiveOcsAdapter(BalancePort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        return await get_json(self._base, f"/balance/{customer_id}")

    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/topup", {
            "customer_id": customer_id, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")

    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        await post_json(self._base, "/addon", {
            "customer_id": customer_id, "addon_id": addon_id, "idempotency_key": key.value,
        })