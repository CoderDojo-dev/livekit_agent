"""Balance/consumption (OCS) adapter implementing BalancePort (scaffold)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.balance import BalancePort
from domain_core.value_objects import IdempotencyKey, Money


class OcsAdapter(BalancePort):
    """Talks to the OCS. Concrete I/O lands in Phases 5/7."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        raise NotImplementedError("wired in Phase 5")

    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        raise NotImplementedError("wired in Phase 7")

    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        raise NotImplementedError("wired in Phase 7")