"""Interruption-safe specialist handoffs from Triage.

A LiveKit handoff must return the next Agent itself. Returning a tuple is treated
as ordinary tool data and can leave the tool-response speech lifecycle stuck.
"""
from __future__ import annotations

from agents.billing_agent import BillingAgent
from agents.technical_agent import TechnicalAgent
from livekit.agents import Agent, RunContext, function_tool

from tools.voice_flow import current_chat_ctx, handoff_with_message


@function_tool()
async def route_to_billing(context: RunContext) -> Agent:
    """Hand off to the billing specialist while preserving conversation history."""
    next_agent = BillingAgent(chat_ctx=current_chat_ctx(context))
    return await handoff_with_message(
        context,
        next_agent,
        "Je vous mets en relation avec notre spécialiste de la facturation.",
    )


@function_tool()
async def route_to_technical(context: RunContext) -> Agent:
    """Hand off to the technical specialist while preserving conversation history."""
    next_agent = TechnicalAgent(chat_ctx=current_chat_ctx(context))
    return await handoff_with_message(
        context,
        next_agent,
        "Je vous mets en relation avec notre spécialiste technique.",
    )
