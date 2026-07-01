"""TriageAgent: consent, greet, answer FAQs, route, escalate — now sentiment-aware (Phase 8).

Inherits BaseTelecomAgent (per-turn sentiment + proactive de-escalation). Ambiguity is handled
through request_clarification so the section 10.1 "two failed clarifications" trigger is deterministic.
"""
from __future__ import annotations

from config.language_presets import GREETINGS
from agents.base_agent import BaseTelecomAgent
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.consent_task import ConsentTask
from tools.clarification_tools import request_clarification
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing, route_to_technical

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and either answer or route. "
    "For general questions about offers, plans, procedures, or FAQs, call knowledge_search "
    "with a concise ENGLISH query and answer in the caller's language, citing the source. "
    "For the caller's own billing/payment, call route_to_billing. For SIM/network/connectivity, "
    "call route_to_technical. For a human, call escalate_to_manager. "
    "If the request is ambiguous, call request_clarification with a single clarifying question "
    "(do not ask directly); if it returns 'escalate', call escalate_to_manager - do not guess again. "
    "If the caller becomes upset, acknowledge it and offer a human. "
    "Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent data."
)


class TriageAgent(BaseTelecomAgent):
    """Default starting persona. Captures consent, greets by name, answers FAQs, routes, escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[
                request_clarification,
                route_to_billing,
                route_to_technical,
                escalate_to_manager,
                build_knowledge_toolset(),
            ],
        )
        self._language = language

    async def on_enter(self) -> None:
        """Collect recording consent (once), then greet — personalized when the caller is known."""
        user_data = self.session.userdata
        if user_data.recording_consent is None:
            granted = await ConsentTask(chat_ctx=self.chat_ctx)
            user_data.recording_consent = bool(granted)

        customer = user_data.customer_context
        if customer is not None:
            instructions = (
                f"Greet the caller by their first name (full name on file: {customer.full_name}), "
                "briefly, and ask how you can help today, in their language. "
                "Do not ask who they are - you already know."
            )
        else:
            instructions = GREETINGS.get(self._language, GREETINGS["fr"])
        self.session.generate_reply(instructions=instructions)