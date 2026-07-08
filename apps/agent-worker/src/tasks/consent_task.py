"""Recording-consent task (CDC 8.1). Bounded: self-completes if no clear answer arrives."""
from __future__ import annotations

import asyncio
import logging

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

CONSENT_DEADLINE_S = 20.0  # no clear yes/no within this -> proceed WITHOUT recording


class ConsentTask(AgentTask[bool]):
    """Captures recording consent, then returns the boolean. Never hangs."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Before anything else, ask the caller - briefly and in their language - for "
                "consent to record the call for quality and security purposes. Wait for a clear "
                "yes or no, then record it. Do not start solving their request yet."
            ),
            chat_ctx=chat_ctx,
        )
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        self._arm()
        try:
            await self.session.generate_reply(
                instructions="Ask the caller, briefly and in their language, for consent to record the call.",
            )
        except Exception as exc:
            logger.warning("consent prompt failed: %s", exc)
            self._finish(False)

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(CONSENT_DEADLINE_S)
        except asyncio.CancelledError:
            return
        if not self._done:
            try:
                await self.session.say(
                    "Je n'ai pas eu de réponse claire, je continue sans enregistrement."
                )
            except Exception:
                pass
            self._finish(False)

    def _finish(self, granted: bool) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        user_data = self.session.userdata
        user_data.recording_consent = granted
        writer = getattr(user_data, "conversation_writer", None)
        if writer is not None:
            try:
                customer = getattr(user_data, "customer_context", None)
                writer.record_consent(
                    granted=granted,
                    language=getattr(user_data, "language", None),
                    customer_id=customer.customer_id if customer else None,
                )
            except Exception as exc:
                logger.debug("consent log skipped: %s", exc)
        self.complete(granted)

    @function_tool()
    async def record_consent(self, granted: bool) -> None:
        """Record whether the caller granted consent to record the call."""
        logger.info("record_consent CALLED granted=%s", granted)
        self._finish(granted)
