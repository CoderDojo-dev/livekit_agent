"""Port to the billing system (Blueprint section 7.3)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain_core.value_objects import IdempotencyKey, Money


class BillingPort(ABC):
    """Read invoices and execute payments / deferrals."""

    @abstractmethod
    async def get_open_invoices(self, customer_id: str) -> list[dict[str, Any]]:
        """Return outstanding invoices for ``customer_id``."""

    @abstractmethod
    async def charge(self, customer_id: str, amount: Money, key: IdempotencyKey) -> str:
        """Charge ``amount`` idempotently; return a transaction reference."""

    @abstractmethod
    async def grant_deferral(self, customer_id: str, days: int, key: IdempotencyKey) -> None:
        """Grant a payment deferral of ``days`` days, idempotently."""