"""Deterministic recording consent with a post-playback deadline."""
from __future__ import annotations

import asyncio
import logging

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

CONSENT_DEADLINE_S = 20.0

_PROMPTS = {
    "fr": "Acceptez-vous l'enregistrement de cet appel à des fins de qualité et de sécurité ?",
    "ar": "هل توافق على تسجيل هذه المكالمة لأغراض الجودة والأمان؟",
    "en": "Do you consent to recording this call for quality and security?",
}

_TIMEOUTS = {
    "fr": "Je n'ai pas reçu de réponse claire. Je continue sans enregistrement.",
    "ar": "لم أتلق إجابة واضحة. سأتابع بدون تسجيل.",
    "en": "I did not receive a clear answer. I will continue without recording.",
}


class ConsentTask(AgentTask[bool]):
    """Capture recording consent without an LLM-generated prompt."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Interpret only a clear yes or no about call recording. "
                "Call record_consent exactly once. Do not answer any other request."
            ),
            chat_ctx=chat_ctx,
        )
        self._done = False
        self._watchdog: asyncio.Task | None = None

    def _language(self) -> str:
        language = getattr(self.session.userdata, "language", "fr")
        return language if language in _PROMPTS else "fr"

    async def on_enter(self) -> None:
        language = self._language()
        try:
            await self.session.say(
                _PROMPTS[language],
                allow_interruptions=True,
            )
        except Exception as exc:
            logger.warning("consent prompt failed: %s", exc)
            self._finish(False)
            return

        # The response timer starts only after the caller heard the question.
        if not self._done:
            self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(CONSENT_DEADLINE_S)
        except asyncio.CancelledError:
            return

        if self._done:
            return

        try:
            await self.session.say(
                _TIMEOUTS[self._language()],
                allow_interruptions=True,
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
        """Record the caller's clear recording-consent decision."""
        self._finish(granted)
