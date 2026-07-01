"""Persona hand-off tools from Triage to specialists (cookbook section 7).

Each returns (NextAgent, transition_line), preserving the one persistent AgentSession.
"""
from __future__ import annotations

from livekit.agents import RunContext, function_tool

from agents.billing_agent import BillingAgent


@function_tool()
async def route_to_billing(context: RunContext) -> tuple[BillingAgent, str]:
    """Hand off to the billing specialist for invoice, payment, or payment-deferral requests."""
    return BillingAgent(), "Let me connect you with our billing specialist."