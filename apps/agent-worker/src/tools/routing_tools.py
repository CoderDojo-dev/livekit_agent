"""Persona hand-off tools from Triage to specialists (cookbook section 7).

Each returns (NextAgent, transition_line), preserving the one persistent AgentSession.
"""
from __future__ import annotations

from agents.billing_agent import BillingAgent
from agents.technical_agent import TechnicalAgent
from livekit.agents import RunContext, function_tool


@function_tool()
async def route_to_billing(context: RunContext) -> tuple[BillingAgent, str]:
    """Hand off to the billing specialist for invoice, payment, or payment-deferral requests."""
    context.session.interrupt()
    return BillingAgent(), "Let me connect you with our billing specialist."


@function_tool()
async def route_to_technical(context: RunContext) -> tuple[TechnicalAgent, str]:
    """Hand off to the technical specialist for SIM, network, or connectivity issues."""
    context.session.interrupt()
    return TechnicalAgent(), "Let me connect you with our technical specialist."