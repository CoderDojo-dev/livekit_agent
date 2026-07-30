"""Explicit payment-amount confirmation (CDC 6.1). Bounded + fail-closed: no confirm, no pay."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

CONFIRM_DEADLINE_S = 25.0  # no clear yes/no within this -> do NOT pay

# Transactional wording is fixed by nature: an amount and a yes/no question. Generating it
# lets the LLM drift in language mid-call and, worse, drift on the amount itself.
_ASK = {
    "fr": "Je confirme un paiement de {amount} dinars sur votre facture. Vous \u00eates d'accord ?",
    "ar": "\u0633\u0623\u0624\u0643\u062f \u062f\u0641\u0639 {amount} \u062f\u064a\u0646\u0627\u0631 \u0639\u0644\u0649 \u0641\u0627\u062a\u0648\u0631\u062a\u0643. \u0647\u0644 \u062a\u0648\u0627\u0641\u0642\u061f",
    "en": "I am confirming a payment of {amount} dinars on your invoice. Do you agree?",
}
_TIMEOUT = {
    "fr": "Je n'ai pas eu votre confirmation, donc je n'ai rien pr\u00e9lev\u00e9. Rien n'a chang\u00e9 sur votre compte.",
    "ar": "\u0644\u0645 \u0623\u062d\u0635\u0644 \u0639\u0644\u0649 \u062a\u0623\u0643\u064a\u062f\u0643\u060c \u0644\u0630\u0644\u0643 \u0644\u0645 \u0623\u0642\u0645 \u0628\u0623\u064a \u062f\u0641\u0639. \u0644\u0645 \u064a\u062a\u063a\u064a\u0631 \u0634\u064a\u0621 \u0641\u064a \u062d\u0633\u0627\u0628\u0643.",
    "en": "I did not get your confirmation, so I have not charged anything. Nothing changed on your account.",
}


def _language(session) -> str:
    """Caller language, defaulting to French. Never raises: a missing field must not
    silence a payment confirmation."""
    lang = getattr(getattr(session, "userdata", None), "language", "fr") or "fr"
    return lang if lang in _ASK else "fr"


class PaymentConfirmTask(AgentTask[bool]):
    """Confirms the exact amount, then returns the boolean. Never hangs; fails closed."""

    def __init__(self, amount: float, currency: str = "TND", chat_ctx=None, tts=None) -> None:
        super().__init__(
            instructions=(
                f"Confirm with the caller that they want to pay {amount:.3f} {currency}. "
                "Ask for an explicit yes or no, in their language. Do not proceed without a clear answer."
            ),
            chat_ctx=chat_ctx,
            tts=tts,
        )
        self._amount = amount
        self._currency = currency
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        lang = _language(self.session)
        await self.session.say(_ASK[lang].format(amount=self._amount))
        self._arm()

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
        return language if language in _TIMEOUT else "fr"

    async def _fail_closed(self) -> None:
        if self._done:
            return
        logger.info("payment confirm fail-closed -> not paying")
        with suppress(Exception):
            await self.session.say(_TIMEOUT[self._language()])
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
