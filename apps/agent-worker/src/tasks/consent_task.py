"""Recording consent task - LiveKit best-practice pattern adapted for telecom FR/AR/EN."""
from __future__ import annotations

import logging

from livekit.agents import AgentTask, RunContext, function_tool

logger = logging.getLogger(__name__)

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


class ConsentTask(AgentTask[bool]):
    """Collect explicit recording consent before proceeding with the call."""

    def __init__(self, language: str = "fr", chat_ctx=None) -> None:
        lang = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[lang]

        super().__init__(
            instructions=(
                f"You MUST speak ONLY in {lang_name}. Never switch language.\n"
                f"Your sole purpose: obtain a clear YES or NO about recording this call.\n"
                f"When the user clearly agrees, call record_consent with consent_given=true.\n"
                f"When the user clearly refuses, call record_consent with consent_given=false.\n"
                f"If the answer is ambiguous, ask again briefly. Stay polite and concise.\n"
                f"Do NOT inform them that the call IS recorded. You MUST ASK for their permission.\n"
                f"Do NOT answer unrelated questions. Do NOT change topic.\n"
                f"Do NOT mention function names or tools in your speech."
            ),
            chat_ctx=chat_ctx,
        )
        self._language = lang
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Ask the consent question with interruptions disabled so the caller hears it fully."""
        prompts = {
            "fr": (
                "Greet briefly in French, then ask:\n"
                "'Cet appel peut être enregistré à des fins de qualité et de sécurité. "
                "Acceptez-vous l'enregistrement ?'\n"
                "Keep it to two sentences maximum. Be warm and professional."
            ),
            "ar": (
                "Greet briefly in Arabic, then ask:\n"
                "'قد يتم تسجيل هذه المكالمة لأغراض الجودة والأمان. "
                "هل توافق على التسجيل؟'\n"
                "Keep it to two sentences maximum. Be warm and professional."
            ),
            "en": (
                "Greet briefly in English, then ask:\n"
                "'This call may be recorded for quality and security purposes. "
                "Do you consent to the recording?'\n"
                "Keep it to two sentences maximum. Be warm and professional."
            ),
        }

        await self.session.generate_reply(
            instructions=prompts[self._language],
            allow_interruptions=False,
        )

    @function_tool()
    async def record_consent(self, context: RunContext, consent_given: bool) -> None:
        """Record the caller's explicit consent decision about call recording.

        Args:
            consent_given: True if the caller explicitly agrees, False if they refuse.
        """
        if consent_given:
            logger.info("caller gave recording consent")
        else:
            logger.info("caller denied recording consent")
            await self.session.generate_reply(
                instructions=(
                    f"In {self._lang_name} only, politely inform the caller that you will "
                    f"continue without recording. Keep it to one short sentence."
                ),
                allow_interruptions=False,
            )

        self.complete(consent_given)
