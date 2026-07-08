"""Explicit payment-amount confirmation (CDC 6.1). Bounded + fail-closed: no confirm, no pay."""
from __future__ import annotations

import asyncio
import logging

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

CONFIRM_DEADLINE_S = 25.0  # no clear yes/no within this -> do NOT pay


class PaymentConfirmTask(AgentTask[bool]):
    """Confirms the exact amount, then returns the boolean. Never hangs; fails closed."""

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
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        self._arm()
        try:
            await self.session.generate_reply(instructions=(
                f"Ask the caller to confirm paying {self._amount:.3f} {self._currency}, in their language."
            ))
        except Exception as exc:
            logger.warning("payment confirm prompt failed: %s", exc)
            await self._fail_closed()

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(CONFIRM_DEADLINE_S)
        except asyncio.CancelledError:
            return
        await self._fail_closed()

    async def _fail_closed(self) -> None:
        if self._done:
            return
        logger.info("payment confirm fail-closed -> not paying")
        try:
            await self.session.say(
                "Je n'ai pas reçu de confirmation claire, je n'effectue pas le paiement."
            )
        except Exception:
            pass
        self._finish(False)

    def _finish(self, confirmed: bool) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        self.complete(confirmed)

    @function_tool()
    async def confirm_payment(self, confirmed: bool) -> None:
        """Record the caller's explicit confirmation (or refusal) of the payment amount."""
        self._finish(confirmed)
