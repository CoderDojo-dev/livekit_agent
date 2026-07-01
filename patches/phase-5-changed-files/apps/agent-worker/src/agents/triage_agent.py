"""TriageAgent: greet (by name), answer FAQs, route, or escalate (Blueprint section 7.1).

Phase 5: knowledge_search (via the scoped MCP toolset) is available so general FAQ/offer/
procedure questions can be answered at triage without a hand-off (CDC section 5.13).
"""
from __future__ import annotations

from livekit.agents import Agent

from config.language_presets import GREETINGS
from mcp_clients.knowledge_glpi_toolset import build_knowledge_toolset
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and either answer or route. "
    "For general questions about offers, plans, procedures, or FAQs, call knowledge_search "
    "with a concise ENGLISH query and answer in the caller's language, citing the source. "
    "For the caller's own billing/payment, call route_to_billing. For a human, call "
    "escalate_to_manager. If the request is ambiguous, ask exactly ONE clarifying question "
    "before guessing; if still unclear, call escalate_to_manager - do not guess a third time. "
    "Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent account data."
)


class TriageAgent(Agent):
    """Default starting persona. Greets by name when known; answers FAQs, routes, or escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[route_to_billing, escalate_to_manager, build_knowledge_toolset()],
        )
        self._language = language

    async def on_enter(self) -> None:
        """Greet the caller, personalized when a Customer-360 snapshot was pre-fetched."""
        ctx = self.session.userdata.customer_context
        if ctx is not None:
            instructions = (
                f"Greet the caller by their first name (full name on file: {ctx.full_name}), "
                "briefly, and ask how you can help today, in their language. "
                "Do not ask who they are - you already know."
            )
        else:
            instructions = GREETINGS.get(self._language, GREETINGS["fr"])
        self.session.generate_reply(instructions=instructions)