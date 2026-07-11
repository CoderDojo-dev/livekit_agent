"""Bounded, localized CIN-last-four verification."""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TASK_DEADLINE_S = 30.0
VERIFY_CALL_TIMEOUT_S = 5.0

_PROMPTS = {
    "fr": "Pour vérifier votre identité, dites uniquement les quatre derniers chiffres de votre CIN.",
    "ar": "للتحقق من هويتك، اذكر فقط آخر أربعة أرقام من بطاقة هويتك.",
    "en": "To verify your identity, say only the last four digits of your national ID.",
}

_RETRY = {
    "fr": "Les chiffres ne correspondent pas. Répétez uniquement les quatre derniers chiffres de votre CIN.",
    "ar": "الأرقام غير مطابقة. أعد ذكر آخر أربعة أرقام فقط.",
    "en": "The digits did not match. Repeat only the last four digits.",
}

_INVALID = {
    "fr": "Je dois recevoir exactement quatre chiffres. Veuillez les répéter lentement.",
    "ar": "يجب أن تذكر أربعة أرقام بالضبط. أعدها ببطء.",
    "en": "I need exactly four digits. Please repeat them slowly.",
}

_SUCCESS = {
    "fr": "Merci, votre identité est confirmée.",
    "ar": "شكراً، تم تأكيد هويتك.",
    "en": "Thank you, your identity is confirmed.",
}

_FAILURE = {
    "fr": "Je n'ai pas pu vérifier votre identité. L'action sensible ne sera pas exécutée.",
    "ar": "تعذر التحقق من هويتك. لن يتم تنفيذ الإجراء الحساس.",
    "en": "I could not verify your identity. The sensitive action will not be executed.",
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
    ) -> None:
        super().__init__(
            instructions=(
                "Collect exactly four CIN digits. "
                "Call verify_with_known_element with only four ASCII digits."
            ),
            chat_ctx=chat_ctx,
        )
        self._customer_id = customer_id
        self._verify_fn = verify_fn
        self._attempts = 0
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
        try:
            await self._speak(_FAILURE)
        except Exception:
            pass
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
