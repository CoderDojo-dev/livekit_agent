"""ManagerAgent: escalation target (Blueprint section 7.1; CDC sections 5.12 / 6.4).

Phase 3 scope: receive an escalated call, reassure the caller, and gather a concise
summary. The live SIP transfer to a human advisor is wired in Phase 8.
"""
from __future__ import annotations

from livekit.agents import Agent


class ManagerAgent(Agent):
    """Single owner of the human-escalation conversation. SIP transfer lands in Phase 8."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You are a senior support manager handling an escalated call. "
                "Acknowledge the escalation, reassure the caller, and gather a concise "
                "summary of their issue so a human advisor can take over. "
                "Always reply in the caller's current language (French, Arabic, or English). "
                "Keep replies short and calm."
            ),
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        """Reassure the caller their issue is being escalated."""
        self.session.generate_reply(
            instructions=(
                "Reassure the caller that their request is being escalated to a specialist, "
                "and briefly confirm what the issue is about, in their language."
            ),
        )