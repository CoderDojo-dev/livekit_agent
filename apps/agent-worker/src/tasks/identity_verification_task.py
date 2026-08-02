"""Bounded, localized CIN-last-four verification."""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable
from contextlib import suppress

from livekit.agents import AgentTask, function_tool
from tools.voice_flow import persona_tts

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
MAX_INVALID_INPUTS = 4
# Timeout hierarchy (invariant): VERIFY_CALL_TIMEOUT_S < TASK_DEADLINE_S < GATE_TIMEOUT_S,
# so the verify call, the whole task, and the surrounding identity gate each fail in order.
TASK_DEADLINE_S = 45.0
VERIFY_CALL_TIMEOUT_S = 5.0

_PROMPTS = {
    "fr": "Avant d'aller plus loin, j'ai juste besoin de m'assurer que c'est bien vous : pouvez-vous me donner les quatre derniers chiffres de votre CIN ?",
    "ar": "قبل أن نكمل، أحتاج فقط للتأكد من أنه أنت: من فضلك أعطني آخر أربعة أرقام من بطاقة هويتك.",
    "en": "Before we go ahead, I just need to make sure it's really you — could you give me the last four digits of your national ID?",
}

_RETRY = {
    "fr": "Ça ne correspond pas de mon côté. On réessaie ensemble : les quatre derniers chiffres de votre CIN, s'il vous plaît.",
    "ar": "الأرقام لا تطابق ما لديّ. لنجرّب مرة أخرى من فضلك: آخر أربعة أرقام من بطاقة هويتك.",
    "en": "That doesn't match what I have here. Let's try once more — the last four digits of your national ID, please.",
}

_INVALID = {
    "fr": "Je n'ai pas bien saisi. Il me faut seulement les quatre derniers chiffres, doucement s'il vous plaît.",
    "ar": "عذرًا، لم أسمعها جيدًا. أحتاج آخر أربعة أرقام فقط، ببطء من فضلك.",
    "en": "Sorry, I didn't quite catch that. I just need the last four digits, slowly if you can.",
}

_SUCCESS = {
    "fr": "Parfait, merci, c'est bien vous. Je continue.",
    "ar": "ممتاز، شكرًا لك، تم التأكد من هويتك. نكمل.",
    "en": "Perfect, thank you — that's confirmed. Let's carry on.",
}

_FAILURE = {
    "fr": "Je suis désolé, je n'arrive pas à confirmer votre identité pour le moment, je ne vais donc pas pouvoir procéder à cette opération. Mais je reste avec vous pour trouver une solution.",
    "ar": "أعتذر، لا أستطيع تأكيد هويتك في الوقت الحالي، لذلك لن أتمكن من إتمام هذه العملية. لكنني سأبقى معك لنجد حلاً.",
    "en": "I'm sorry, I can't confirm your identity right now, so I won't be able to go ahead with this. But I'll stay with you and we'll find a way forward.",
}

_WORD_DIGITS = {
    "zero": "0", "zéro": "0", "صفر": "0",
    "one": "1", "un": "1", "une": "1", "واحد": "1",
    "two": "2", "deux": "2", "اثنان": "2", "اثنين": "2",
    "three": "3", "trois": "3", "ثلاثة": "3",
    "four": "4", "quatre": "4", "أربعة": "4", "اربعة": "4",
    "five": "5", "cinq": "5", "خمسة": "5",
    "six": "6", "ستة": "6",
    "seven": "7", "sept": "7", "سبعة": "7",
    "eight": "8", "huit": "8", "ثمانية": "8",
    "nine": "9", "neuf": "9", "تسعة": "9",
}


def normalize_spoken_digits(value: str) -> str | None:
    """Extract exactly four digits from numeric or spoken FR/AR/EN input."""
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    tokens = re.findall(r"[0-9]+|[^\W\d_]+", normalized, flags=re.UNICODE)

    # Numeric speech wins over spelled-out words. A caller echoing the question
    # ("les QUATRE derniers, c'est 1234") would otherwise inject a fifth digit
    # via _WORD_DIGITS and be asked again for an answer that was already right.
    numeric = [d for token in tokens if token.isdigit() for d in token]
    if len(numeric) == 4:
        return "".join(numeric)

    digits: list[str] = []

    for token in tokens:
        if token.isdigit():
            digits.extend(token)
        elif token in _WORD_DIGITS:
            digits.append(_WORD_DIGITS[token])

    return "".join(digits) if len(digits) == 4 else None


class IdentityVerificationTask(AgentTask[bool]):
    """Verify identity without allowing LLM-selected response languages."""

    def __init__(
        self,
        customer_id: str,
        verify_fn: Callable[[str, str], Awaitable[bool]],
        chat_ctx=None,
        tts=None,
    ) -> None:
        super().__init__(
            instructions=(
                "Collect exactly four CIN digits. "
                "Call verify_with_known_element with only four ASCII digits."
            ),
            chat_ctx=chat_ctx,
            tts=persona_tts(tts),
        )
        self._customer_id = customer_id
        self._verify_fn = verify_fn
        self._attempts = 0
        self._invalid_inputs = 0
        self._done = False
        self._watchdog: asyncio.Task | None = None

    def _language(self) -> str:
        language = getattr(self.session.userdata, "language", "fr")
        return language if language in _PROMPTS else "fr"

    async def _speak(self, messages: dict[str, str]) -> None:
        await self.session.say(
            messages[self._language()],
            allow_interruptions=True,
        )

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def on_enter(self) -> None:
        try:
            await self._speak(_PROMPTS)
        except Exception as exc:
            logger.warning("identity prompt failed: %s", exc)
            await self._fail_closed("prompt_error")
            return

        if not self._done:
            self._arm()

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(TASK_DEADLINE_S)
        except asyncio.CancelledError:
            return
        await self._fail_closed("timeout")

    async def _fail_closed(self, reason: str) -> None:
        if self._done:
            return

        logger.info("identity fail-closed (%s)", reason)
        with suppress(Exception):
            await self._speak(_FAILURE)
        self._finish(False)

    def _finish(self, verified: bool) -> None:
        if self._done:
            return

        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        self.complete(verified)

    @function_tool()
    async def verify_with_known_element(
        self,
        provided_value: str,
    ) -> None:
        """Verify exactly four normalized CIN digits."""
        digits = normalize_spoken_digits(provided_value)

        # Invalid speech does not consume a persisted authentication attempt.
        if digits is None:
            self._invalid_inputs += 1
            if self._invalid_inputs >= MAX_INVALID_INPUTS:
                await self._fail_closed("max_invalid_inputs")
                return
            await self._speak(_INVALID)
            self._arm()
            return

        self._attempts += 1
        self._arm()

        try:
            verified = await asyncio.wait_for(
                self._verify_fn(self._customer_id, digits),
                timeout=VERIFY_CALL_TIMEOUT_S,
            )
        except Exception as exc:
            logger.warning(
                "verify_fn failed (attempt %s): %s",
                self._attempts,
                exc,
            )
            verified = False

        if verified:
            await self._speak(_SUCCESS)
            self._finish(True)
            return

        if self._attempts >= MAX_ATTEMPTS:
            await self._fail_closed("max_attempts")
            return

        await self._speak(_RETRY)
