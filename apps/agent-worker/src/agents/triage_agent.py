"""Triage agent: consent, greeting, FAQ lookup, routing, and escalation."""
from __future__ import annotations

import logging

from agents.base_agent import BaseTelecomAgent
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.consent_task import ConsentTask
from tools.clarification_tools import request_clarification
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing, route_to_technical

logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom customer-support line. "
    "Determine the caller's need and either answer or route it. "
    "For general offers, procedures, and FAQs, call knowledge_search with a "
    "concise English query, then answer in {language} and cite the source. "
    "For personal billing, invoices, balances, or payments, call "
    "route_to_billing. For SIM, network, or connectivity issues, call "
    "route_to_technical. For a human advisor, call escalate_to_manager. "
    "For an ambiguous request, call request_clarification. "
    "Always reply only in {language}. Keep replies short. Never invent data. "
    "Do not reveal a customer's name or personal details before identity "
    "verification succeeds."
)

_GREETINGS = {
    "fr": "Bonjour. Comment puis-je vous aider aujourd'hui ?",
    "ar": "مرحباً. كيف يمكنني مساعدتك اليوم؟",
    "en": "Hello. How can I help you today?",
}


class TriageAgent(BaseTelecomAgent):
    """Starting persona for consent, triage, FAQ, and specialist routing."""

    def __init__(self, language: str = "fr") -> None:
        selected_language = (
            language if language in _GREETINGS else "fr"
        )
        super().__init__(
            instructions=_INSTRUCTIONS.format(
                language={
                    "fr": "French",
                    "ar": "Arabic",
                    "en": "English",
                }[selected_language]
            ),
            tools=[
                request_clarification,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )
        self._language = selected_language

    async def on_enter(self) -> None:
        """Collect consent, then greet without disclosing customer PII."""
        logger.info(
            "triage agent entered language=%s",
            self._language,
        )
        user_data = self.session.userdata

        if user_data.recording_consent is None:
            granted = await ConsentTask(chat_ctx=self.chat_ctx)
            user_data.recording_consent = bool(granted)

        await self.session.say(
            _GREETINGS[self._language],
            allow_interruptions=True,
        )
