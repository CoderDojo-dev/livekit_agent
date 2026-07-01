"""Port to the balance / consumption system (OCS) (Blueprint section 7.4)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.value_objects import IdempotencyKey, Money


class BalancePort(ABC):
    """Read balance/consumption and apply recharges / add-ons."""

    @abstractmethod
    async def get_balance(self, customer_id: str) -> dict[str, Any]:
        """Return balance and data consumption for ``customer_id``."""

    @abstractmethod
    async def top_up(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        """Recharge ``amount`` idempotently; return a reference."""

    @abstractmethod
    async def apply_data_addon(self, customer_id: str, addon_id: str, key: IdempotencyKey) -> None:
        """Apply a complementary data add-on idempotently."""