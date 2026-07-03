"""Payment gateway adapter implementing PaymentPort (report #3)."""
from __future__ import annotations

from domain_core.ports.payment import PaymentPort
from domain_core.value_objects import IdempotencyKey, Money
from integration_adapters._http import post_json


class MockPaymentAdapter(PaymentPort):
    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        return f"PAY-{key.value[:10].upper()}"


class LivePaymentAdapter(PaymentPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def pay(self, token: str, amount: Money, key: IdempotencyKey) -> str:
        data = await post_json(self._base, "/pay", {
            "token": token, "amount": str(amount.amount),
            "currency": amount.currency, "idempotency_key": key.value,
        })
        return data.get("reference", "")