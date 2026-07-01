"""TriageAgent: consent, greet (by name), answer FAQs, route, or escalate (Blueprint section 7.1).

Phase 7: collects recording consent first (ConsentTask, CDC 8.1), then greets; routes to the
Billing or Technical specialist, answers FAQs via knowledge_search, or escalates.
"""
from __future__ import annotations

from livekit.agents import Agent

from config.language_presets import GREETINGS
from mcp_clients.knowledge_toolset import build_knowledge_toolset
from tasks.consent_task import ConsentTask
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing, route_to_technical

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and either answer or route. "
    "For general questions about offers, plans, procedures, or FAQs, call knowledge_search "
    "with a concise ENGLISH query and answer in the caller's language, citing the source. "
    "For the caller's own billing/payment, call route_to_billing. For SIM/network/connectivity, "
    "call route_to_technical. For a human, call escalate_to_manager. If the request is "
    "ambiguous, ask exactly ONE clarifying question before guessing; if still unclear, call "
    "escalate_to_manager - do not guess a third time. Always reply in the caller's current "
    "language ({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent data."
)


class TriageAgent(Agent):
    """Default starting persona. Captures consent, greets by name, answers FAQs, routes, escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[route_to_billing, route_to_technical, escalate_to_manager, build_knowledge_toolset()],
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