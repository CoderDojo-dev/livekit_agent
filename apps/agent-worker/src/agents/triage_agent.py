"""Triage agent: consent, greeting, FAQ lookup, routing, and escalation."""

from __future__ import annotations

import logging

from mcp_clients.knowledge_toolset import build_knowledge_toolset
from providers.tts import build_persona_tts
from tasks.consent_task import ConsentTask
from tools.clarification_tools import request_clarification
from tools.voice_flow import persona_tts
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import (
    route_to_account_services,
    route_to_billing,
    route_to_technical,
)

from agents.base_agent import KNOWLEDGE_ABSTENTION_RULE, BaseTelecomAgent, merge_instructions

logger = logging.getLogger(__name__)

_LANG_NAMES = {"fr": "French", "ar": "Arabic", "en": "English"}

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom customer-support line. "
    "You MUST speak ONLY in {language}. Never switch to another language.\n"
    "Determine the caller's need and either answer or route it.\n"
    "For general offers, procedures, and FAQs, call knowledge_search with a "
    "concise English query, then answer in {language} and cite the source.\n"
    "For personal billing, invoices, balances, or payments, call route_to_billing.\n"
    "For SIM, network, or connectivity issues, call route_to_technical.\n"
    "For the caller's phone line, phone number, plan, recharge, or roaming, "
    "call route_to_account_services.\n"
    "For a human advisor, call escalate_to_manager.\n"
    "For an ambiguous request, call request_clarification.\n"
    "Keep replies short. Never invent data.\n"
    "Do not reveal a customer's name or personal details before identity "
    "verification succeeds."
)


class TriageAgent(BaseTelecomAgent):
    """Starting persona for consent, triage, FAQ, and specialist routing."""

    def __init__(self, language: str = "fr") -> None:
        selected_language = language if language in _LANG_NAMES else "fr"
        lang_name = _LANG_NAMES[selected_language]

        super().__init__(
            instructions=merge_instructions(
                _INSTRUCTIONS.format(language=lang_name) + "\n\n" + KNOWLEDGE_ABSTENTION_RULE,
            ),
            tools=[
                request_clarification,
                route_to_account_services,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
            tts=build_persona_tts(selected_language, "triage"),
        )
        self._language = selected_language
        self._lang_name = lang_name

    async def on_enter(self) -> None:
        """Collect consent, then greet without disclosing customer PII."""
        logger.info("triage agent entered language=%s", self._language)
        user_data = self.session.userdata

        if user_data.recording_consent is None:
            granted = await ConsentTask(
                language=self._language,
                chat_ctx=self.chat_ctx.copy(exclude_instructions=True),
                tts=persona_tts(self.tts),
            )
            user_data.recording_consent = bool(granted)
            consent_just_collected = True
        else:
            consent_just_collected = False

        # Acknowledge the consent answer AND offer help in ONE short turn (no
        # duplicate greeting, no lag). Consent stays owned by ConsentTask above.
        if consent_just_collected and user_data.recording_consent:
            ack = (
                f"In {self._lang_name} only: warmly THANK the caller for agreeing, "
                f"then ask how you can help today. Two short sentences. Do NOT "
                f"mention the caller's name or any personal details."
            )
        elif consent_just_collected and not user_data.recording_consent:
            ack = (
                f"In {self._lang_name} only: acknowledge respectfully that you will "
                f"continue WITHOUT recording, then ask how you can help today. Two "
                f"short sentences. Do NOT mention the caller's name or any personal details."
            )
        else:
            ack = (
                f"In {self._lang_name} only, ask how you can help today. One short "
                f"sentence. Do NOT mention the caller's name or any personal details."
            )
        await self.session.generate_reply(instructions=ack)
