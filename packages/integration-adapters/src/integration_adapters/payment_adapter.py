"""Payment gateway adapter implementing PaymentPort (scaffold)."""
from __future__ import annotations

from domain_core.ports.payment import PaymentPort
from domain_core.value_objects import IdempotencyKey, Money


class PaymentAdapter(PaymentPort):
    """Talks to the PSP. Concrete I/O lands in Phase 7."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        raise NotImplementedError("wired in Phase 7")