"""Recording consent task - LiveKit best-practice pattern adapted for telecom FR/AR/EN."""

from __future__ import annotations

import logging

from livekit.agents import AgentTask, RunContext, function_tool
from tools.voice_flow import persona_tts

logger = logging.getLogger(__name__)

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}


class ConsentTask(AgentTask[bool]):
    """Collect explicit recording consent before proceeding with the call."""

    def __init__(self, language: str = "fr", chat_ctx=None, tts=None) -> None:
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
            tts=persona_tts(tts),
        )
        self._language = lang
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Ask the consent question with interruptions disabled so the caller hears it fully."""
        prompts = {
            "fr": (
                "Speak ONLY in French, warm and professional. In ONE short turn:\n"
                "1) Briefly greet and introduce yourself as the customer-support "
                "virtual assistant, here to help.\n"
                "2) Ask permission to record the call for quality assurance and "
                "supervision, and make clear they are FREE TO DECLINE.\n"
                "3) Invite a clear yes or no.\n"
                "Three short sentences maximum. You are ASKING permission — never "
                "state that the call is already being recorded."
            ),
            "ar": (
                "Speak ONLY in Arabic, warm and professional. In ONE short turn: "
                "briefly greet and introduce yourself as the support assistant; "
                "ask permission to record the call for quality and supervision, "
                "making clear they are free to decline; invite a clear yes or no. "
                "Three short sentences max. You are ASKING — do not say it is already recorded."
            ),
            "en": (
                "Speak ONLY in English, warm and professional. In ONE short turn: "
                "briefly greet and introduce yourself as the support assistant; "
                "ask permission to record the call for quality assurance and "
                "supervision, making clear they are free to decline; invite a clear "
                "yes or no. Three short sentences max. You are ASKING — never state "
                "the call is already being recorded."
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

        # No spoken reply here: keep consent collection cleanly SEPARATED from the
        # conversation flow. The collecting agent acknowledges the decision
        # (thank + proceed / proceed-without-recording) once control returns.
        self.complete(consent_given)
