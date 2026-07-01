"""Port to the payment gateway (Blueprint section 7.8)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.value_objects import IdempotencyKey, Money


class PaymentPort(ABC):
    """Execute confirmed payments through the PSP."""

    @abstractmethod
    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        """Process a payment idempotently; return a transaction reference."""