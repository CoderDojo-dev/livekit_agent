"""TriageAgent: entry persona — greet (by name when known), classify, route (Blueprint section 7.1).

Phase 4: greets using the pre-fetched Customer-360 snapshot, and routes to the Billing
specialist or escalates. Ambiguity rule (one clarifying question, then escalate) from Phase 3.
"""
from __future__ import annotations

from livekit.agents import Agent

from config.language_presets import GREETINGS
from tools.escalation_tools import escalate_to_manager
from tools.routing_tools import route_to_billing

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and route to the right specialist "
    "(billing/payment via route_to_billing, or a human via escalate_to_manager). "
    "If the request is ambiguous, ask exactly ONE clarifying question before guessing. "
    "If it is still unclear after that single follow-up, call escalate_to_manager - "
    "do not guess a third time. Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English). Keep replies short. Do not invent account data."
)


class TriageAgent(Agent):
    """Default starting persona. Greets by name when the caller is known; routes or escalates."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[route_to_billing, escalate_to_manager],
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