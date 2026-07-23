"""Interruption-safe specialist handoffs from Triage.

A LiveKit handoff must return the next Agent itself. Returning a tuple is treated
as ordinary tool data and can leave the tool-response speech lifecycle stuck.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from livekit.agents import Agent, RunContext, function_tool

from tools.voice_flow import current_chat_ctx, handoff_with_message

if TYPE_CHECKING:
    pass


def _resolve_language(context: RunContext) -> str:
    user_data = getattr(context.session, "userdata", None)
    if user_data is not None:
        lang = getattr(user_data, "language", "fr")
        val = getattr(lang, "value", lang)
        if isinstance(val, str) and val.lower().strip()[:2] in {"fr", "ar", "en"}:
            return val.lower().strip()[:2]
    return "fr"


# Phrases de transition DÉTERMINISTES (par cible / langue). Déterministe = pas
# d'hallucination, pas de tour LLM parasite, cohérent à chaque appel.
_ROUTE_LINES = {
    "billing": {
        "fr": "Très bien, je vous mets en relation avec notre service de facturation.",
        "ar": "حسنًا، سأحوّلك إلى قسم الفوترة لدينا.",
        "en": "Sure, I'm connecting you with our billing department.",
    },
    "technical": {
        "fr": "Très bien, je vous mets en relation avec notre service technique.",
        "ar": "حسنًا، سأحوّلك إلى الدعم الفني لدينا.",
        "en": "Sure, I'm connecting you with our technical support.",
    },
    "account": {
        "fr": "Très bien, je vous mets en relation avec notre service de gestion de compte.",
        "ar": "حسنًا، سأحوّلك إلى قسم إدارة الحساب لدينا.",
        "en": "Sure, I'm connecting you with our account services team.",
    },
}


@function_tool()
async def route_to_billing(context: RunContext) -> Agent:
    """Hand off to the billing specialist while preserving conversation history."""
    from agents.billing_agent import BillingAgent

    lang = _resolve_language(context)
    agent = BillingAgent(chat_ctx=current_chat_ctx(context), language=lang)
    return await handoff_with_message(context, agent, _ROUTE_LINES["billing"][lang])


@function_tool()
async def route_to_technical(context: RunContext) -> Agent:
    """Hand off to the technical specialist while preserving conversation history."""
    from agents.technical_agent import TechnicalAgent

    lang = _resolve_language(context)
    agent = TechnicalAgent(chat_ctx=current_chat_ctx(context), language=lang)
    return await handoff_with_message(context, agent, _ROUTE_LINES["technical"][lang])


@function_tool()
async def route_to_account_services(context: RunContext) -> Agent:
    """Hand off account, plan, phone-line, recharge, and roaming requests."""
    from agents.account_services_agent import AccountServicesAgent

    lang = _resolve_language(context)
    agent = AccountServicesAgent(chat_ctx=current_chat_ctx(context), language=lang)
    return await handoff_with_message(context, agent, _ROUTE_LINES["account"][lang])
