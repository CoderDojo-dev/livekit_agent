"""Explicit payment-amount confirmation (CDC section 6.1). Runs before EXECUTE_PAYMENT.

Verbal confirmation is mandatory; the policy engine REFUSES a payment without it, so this task
captures the caller's yes/no and passes it into the guarded action.
"""
from __future__ import annotations

from livekit.agents import AgentTask, function_tool


class PaymentConfirmTask(AgentTask[bool]):
    """Takes over the session to confirm the exact amount, then returns the boolean."""

    def __init__(self, amount: float, currency: str = "TND", chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                f"Confirm with the caller that they want to pay {amount:.3f} {currency}. "
                "Ask for an explicit yes or no, in their language. Do not proceed without a clear answer."
            ),
            chat_ctx=chat_ctx,
        )
        self._amount = amount
        self._currency = currency

    async def on_enter(self) -> None:
        """Ask the caller to confirm the exact amount."""
        await self.session.generate_reply(
            instructions=(
                f"Ask the caller to confirm paying {self._amount:.3f} {self._currency}, in their language."
            ),
        )

    @function_tool()
    async def confirm_payment(self, confirmed: bool) -> None:
        """Record the caller's explicit confirmation (or refusal) of the payment amount."""
        self.complete(confirmed)