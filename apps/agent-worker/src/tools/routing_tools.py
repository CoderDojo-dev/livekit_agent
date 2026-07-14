"""Interruption-safe specialist handoffs from Triage.

A LiveKit handoff must return the next Agent itself. Returning a tuple is treated
as ordinary tool data and can leave the tool-response speech lifecycle stuck.
"""
from __future__ import annotations

from agents.account_services_agent import AccountServicesAgent
from agents.billing_agent import BillingAgent
from agents.technical_agent import TechnicalAgent
from livekit.agents import Agent, RunContext, function_tool

from tools.voice_flow import current_chat_ctx


def _resolve_language(context: RunContext) -> str:
    user_data = getattr(context.session, "userdata", None)
    if user_data is not None:
        lang = getattr(user_data, "language", "fr")
        val = getattr(lang, "value", lang)
        if isinstance(val, str) and val.lower().strip()[:2] in {"fr", "ar", "en"}:
            return val.lower().strip()[:2]
    return "fr"


@function_tool()
async def route_to_billing(context: RunContext) -> Agent:
    """Hand off to the billing specialist while preserving conversation history."""
    return BillingAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))


@function_tool()
async def route_to_technical(context: RunContext) -> Agent:
    """Hand off to the technical specialist while preserving conversation history."""
    return TechnicalAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))


@function_tool()
async def route_to_account_services(context: RunContext) -> Agent:
    """Hand off account, plan, phone-line, recharge, and roaming requests."""
    return AccountServicesAgent(chat_ctx=current_chat_ctx(context), language=_resolve_language(context))
