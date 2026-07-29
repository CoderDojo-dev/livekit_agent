"""Explicit payment-amount confirmation (CDC 6.1). Bounded + fail-closed: no confirm, no pay."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from livekit.agents import AgentTask, function_tool
from tools.voice_flow import persona_tts

logger = logging.getLogger(__name__)

CONFIRM_DEADLINE_S = 25.0  # no clear yes/no within this -> do NOT pay

# Repli parlé, déterministe et localisé. Le littéral était codé en dur en
# français : un appelant AR/EN l'entendait en français, en pleine voix de
# persona. Même forme que IdentityVerificationTask (dict + _language()).
_NO_CONFIRMATION = {
    "fr": "Je n'ai pas eu de confirmation claire, alors je préfère ne rien débiter. On pourra reprendre dès que vous voulez.",
    "ar": "لم أحصل على تأكيد واضح، لذلك أفضّل ألا أنفّذ الدفع. يمكننا المحاولة مجددًا وقتما تشاء.",
    "en": "I didn't get a clear confirmation, so I'd rather not take the payment. We can go through it again whenever you're ready.",
}


class PaymentConfirmTask(AgentTask[bool]):
    """Confirms the exact amount, then returns the boolean. Never hangs; fails closed."""

    def __init__(self, amount: float, currency: str = "TND", chat_ctx=None, tts=None) -> None:
        super().__init__(
            instructions=(
                f"Confirm with the caller that they want to pay {amount:.3f} {currency}. "
                "Ask for an explicit yes or no, in their language. Do not proceed without a clear answer."
            ),
            chat_ctx=chat_ctx,
            tts=persona_tts(tts),
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

    def _language(self) -> str:
        language = getattr(self.session.userdata, "language", "fr")
        return language if language in _NO_CONFIRMATION else "fr"

    async def _fail_closed(self) -> None:
        if self._done:
            return
        logger.info("payment confirm fail-closed -> not paying")
        with suppress(Exception):
            await self.session.say(_NO_CONFIRMATION[self._language()])
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
