"""Escalation tool facades (Blueprint section 7; cookbook section 7).

escalate_to_manager is the shared hand-off tool reused by every persona: it returns the
next agent + a transition line, preserving the single persistent AgentSession. SIP transfer
and callback scheduling land in Phase 8.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from agents.manager_agent import ManagerAgent


@function_tool()
async def escalate_to_manager(context: RunContext) -> tuple[ManagerAgent, str]:
    """Hand off to a manager when the caller asks for a human, when the situation requires
    it, or when triage cannot resolve the request after one clarifying question."""
    return ManagerAgent(), "I'm connecting you with a specialist now."


async def transfer_to_human(reason: str) -> dict:
    """Warm/cold SIP transfer to a human endpoint (Phase 8)."""
    raise NotImplementedError("wired in Phase 8 (Sentiment & Escalation)")


async def schedule_callback(when: str) -> dict:
    """Offer a callback when no advisor is available (Phase 8)."""
    raise NotImplementedError("wired in Phase 8 (Sentiment & Escalation)")