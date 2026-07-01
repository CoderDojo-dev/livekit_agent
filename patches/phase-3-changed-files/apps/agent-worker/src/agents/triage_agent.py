"""TriageAgent: entry persona — greet, classify, and hand off (Blueprint section 7.1).

Phase 3 adds ambiguity handling (exactly ONE clarifying question, then escalate) and the
shared escalate_to_manager hand-off tool. No business logic lives here; sensitive work is
delegated to tools in later phases. Instructions are written ONCE in English with an
explicit reply-in-the-caller's-language rule (cookbook section 1.2).
"""
from __future__ import annotations

from livekit.agents import Agent

from config.language_presets import GREETINGS
from tools.escalation_tools import escalate_to_manager

_INSTRUCTIONS = (
    "You are the first point of contact on a telecom operator's customer-support line. "
    "Greet the caller, determine their need, and route to the right specialist "
    "(billing, technical/SIM, account/plan, or a human manager). "
    "If the request is ambiguous, ask exactly ONE clarifying question before guessing. "
    "If it is still unclear after that single follow-up, call escalate_to_manager - "
    "do not guess a third time. Always reply in the caller's current language "
    "({language}: fr=French, ar=Arabic, en=English), as detected from their speech. "
    "Keep replies short and natural for speech. Do not invent account data."
)


class TriageAgent(Agent):
    """Default starting persona. Greets on entry; escalates rather than guessing."""

    def __init__(self, language: str = "fr") -> None:
        super().__init__(
            instructions=_INSTRUCTIONS.format(language=language),
            tools=[escalate_to_manager],
        )
        self._language = language

    async def on_enter(self) -> None:
        """Greet the caller in the session language as soon as the agent is active."""
        self.session.generate_reply(
            instructions=GREETINGS.get(self._language, GREETINGS["fr"]),
        )