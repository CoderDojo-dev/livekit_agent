"""ManagerAgent: escalation target — transfer or callback, and open a follow-up ticket (Phase 9).

Inherits BaseTelecomAgent. Reached on the shared session (full context). Can open a ticket so an
escalated issue is tracked and the caller gets a written confirmation.
"""
from __future__ import annotations

from mcp_clients.ticketing_toolset import build_ticketing_toolset
from telephony.sip_transfer import transfer_to_human

from agents.base_agent import BaseTelecomAgent


class ManagerAgent(BaseTelecomAgent):
    """Single owner of human escalation: transfer/callback, plus follow-up ticketing."""

    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "You are a senior support manager handling an escalated call. "
                "Call transfer_to_human immediately and do not speak before calling it. "
                "The transfer tool owns the single transition announcement and will schedule a callback "
                "if none is free). If the issue needs tracking, call create_ticket (with the "
                "caller's language) so they receive a written confirmation, and give them the "
                "reference. Keep replies short and calm; always reply in the caller's language."
            ),
            chat_ctx=chat_ctx,
            tools=[transfer_to_human, build_ticketing_toolset()],
        )

    async def on_enter(self) -> None:
        """Start the transfer without generating a second transition message."""
        self.session.generate_reply(
            instructions=(
                "Call transfer_to_human now. Do not produce spoken text before the tool call."
            ),
        )