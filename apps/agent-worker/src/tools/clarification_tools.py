"""Deterministic, interruption-safe clarification and escalation.

The first clarification is spoken directly, then StopResponse terminates the
tool-only turn without creating an empty LLM-to-TTS stream. The second failed
clarification performs the real manager handoff rather than returning an
instruction and hoping the LLM calls another tool.
"""
from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from tools.escalation_tools import escalate_to_manager
from tools.voice_flow import say_and_stop


@function_tool()
async def request_clarification(
    context: RunContext,
    question: str,
) -> Agent | None:
    """Ask one clarification. Escalate deterministically after the second attempt."""
    user_data = context.session.userdata
    user_data.clarification_attempts += 1

    if user_data.clarification_attempts >= 2:
        return await escalate_to_manager(context)

    normalized = (question or "").strip()
    if not normalized:
        normalized = "Pouvez-vous préciser votre demande, s'il vous plaît ?"

    await say_and_stop(context, normalized)

    # say_and_stop always raises StopResponse. This keeps the annotation explicit.
    return None
