"""ManagerAgent: escalation target — reached with full context, transfers or schedules a callback.

(Blueprint section 7.1; CDC section 5.12 / 6.4.) The shared AgentSession preserves the prior
conversation, so the Manager has the caller's context on hand-off.
"""
from __future__ import annotations

from livekit.agents import Agent
from agents.base_agent import BaseTelecomAgent

from telephony.sip_transfer import transfer_to_human


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer to an advisor or schedule a callback."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You are a senior support manager handling an escalated call. Briefly acknowledge "
                "and reassure the caller, confirm the issue in one sentence, then use "
                "transfer_to_human to connect them to a live advisor (it will schedule a callback "
                "if none is free). Keep replies short and calm, and always reply in the caller's "
                "current language."
            ),
            chat_ctx=chat_ctx,
            tools=[transfer_to_human],
        )

    async def on_enter(self) -> None:
        """Reassure the caller and move to connect a human."""
        self.session.generate_reply(
            instructions=(
                "Reassure the caller their issue is being escalated, confirm briefly what it is "
                "about, and tell them you will connect them with a human advisor now, in their language."
            ),
        )
