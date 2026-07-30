"""The persona contract: no persona may be instructed to use a tool it lacks.

Pure tests -- they exercise the instruction builder against declared tool-name
sets, with no LiveKit session and no TTS provider.
scripts/persona_contract_checks.py asserts that PERSONA_TOOLSETS below stays in
sync with the real persona files, so this mirror cannot silently rot.
"""

from __future__ import annotations

import pytest

from agents.account_services_agent import _CORE as ACCOUNT_CORE
from agents.billing_agent import _CORE as BILLING_CORE
from agents.domains import DOMAIN_BY_KEY, DOMAINS, SUPPORTED_LANGUAGES
from agents.instruction_kit import (
    build_persona_instructions,
    instruction_violations,
    routing_mandate,
    tool_names,
)
from agents.manager_agent import _CORE as MANAGER_CORE
from agents.technical_agent import _CORE as TECHNICAL_CORE
from agents.triage_agent import _INSTRUCTIONS as TRIAGE_CORE

AUTO_INJECTED = {"end_conversation", "switch_spoken_language"}

# Mirror of each persona's registered tools (+ declared capabilities).
PERSONA_TOOLSETS: dict[str, frozenset[str]] = {
    "TriageAgent": frozenset(
        {
            "request_clarification",
            "check_customer_tickets",
            "get_ticket_state",
            "route_to_account_services",
            "route_to_billing",
            "route_to_technical",
            "escalate_to_manager",
            "knowledge_search",
        }
        | AUTO_INJECTED
    ),
    "BillingAgent": frozenset(
        {
            "get_invoice_summary",
            "get_balance_summary",
            "make_payment",
            "request_payment_deferral",
            "route_to_account_services",
            "route_to_technical",
            "escalate_to_manager",
            "knowledge_search",
        }
        | AUTO_INJECTED
    ),
    "AccountServicesAgent": frozenset(
        {
            "get_plan_details",
            "change_plan",
            "top_up",
            "toggle_roaming",
            "get_balance_summary",
            "get_invoice_summary",
            "route_to_billing",
            "route_to_technical",
            "escalate_to_manager",
            "knowledge_search",
        }
        | AUTO_INJECTED
    ),
    "TechnicalAgent": frozenset(
        {
            "unblock_sim",
            "replace_sim",
            "diagnose_data_issue",
            "check_network_status",
            "route_to_account_services",
            "route_to_billing",
            "escalate_to_manager",
            "create_support_ticket",
            "check_customer_tickets",
            "get_ticket_state",
            "mark_ticket_resolved",
            "update_support_ticket",
            "delete_support_ticket",
            "knowledge_search",
        }
        | AUTO_INJECTED
    ),
    "ManagerAgent": frozenset(
        {
            "transfer_to_human",
            "create_support_ticket",
            "check_customer_tickets",
            "get_ticket_state",
        }
        | AUTO_INJECTED
    ),
}

PERSONA_CORES: dict[str, str] = {
    "TriageAgent": TRIAGE_CORE.format(language="French"),
    "BillingAgent": BILLING_CORE.format(lang_name="French"),
    "AccountServicesAgent": ACCOUNT_CORE.format(lang_name="French"),
    "TechnicalAgent": TECHNICAL_CORE.format(lang_name="French"),
    "ManagerAgent": MANAGER_CORE.format(lang_name="French"),
}

OWNED_DOMAIN_TOOL = {
    "BillingAgent": "route_to_billing",
    "AccountServicesAgent": "route_to_account_services",
    "TechnicalAgent": "route_to_technical",
}


def _instructions(persona: str) -> str:
    return build_persona_instructions(
        PERSONA_CORES[persona], PERSONA_TOOLSETS[persona], tts_provided=True
    )


# --- Invariant central ------------------------------------------------------ #


@pytest.mark.parametrize("persona", sorted(PERSONA_TOOLSETS))
def test_no_persona_is_told_to_use_a_tool_it_lacks(persona: str) -> None:
    """The v64 invariant. This is the test that would have caught the v63 bug."""
    assert instruction_violations(_instructions(persona), PERSONA_TOOLSETS[persona]) == []


@pytest.mark.parametrize("persona,route_tool", sorted(OWNED_DOMAIN_TOOL.items()))
def test_owned_domain_is_never_routed_away(persona: str, route_tool: str) -> None:
    text = _instructions(persona)
    assert route_tool not in text
    assert "YOUR OWN responsibility" in text


def test_triage_still_routes_all_three_domains() -> None:
    text = _instructions("TriageAgent")
    for domain in DOMAINS:
        assert f"call {domain.route_tool} immediately" in text
    assert "call request_clarification" in text
    assert "YOUR OWN responsibility" not in text


def test_manager_gets_the_terminal_mandate() -> None:
    text = _instructions("ManagerAgent")
    assert "FINAL escalation point" in text
    assert "transfer_to_human" in text
    assert "escalate_to_manager" not in text
    assert "YOUR OWN responsibility" not in text


# --- Non-régression du prompt de Triage ------------------------------------- #


def test_triage_mandate_contains_consent_and_no_route_away() -> None:
    """The triage mandate must forbid routing away and require caller consent before escalating."""
    text = routing_mandate(PERSONA_TOOLSETS["TriageAgent"])

    assert "NEVER tell the caller to call a different department" in text
    assert "escalate_to_manager" in text
    assert "caller_agreed" in text
    assert "FINAL escalation point" not in text


# --- Couches dérivées ------------------------------------------------------- #


def test_knowledge_rule_follows_the_declared_capability() -> None:
    assert "GROUND your answer strictly" in _instructions("BillingAgent")
    assert "GROUND your answer strictly" in _instructions("AccountServicesAgent")


def test_clarification_line_degrades_gracefully() -> None:
    assert "call request_clarification" in _instructions("TriageAgent")
    assert "ask the caller ONE short question yourself" in _instructions("BillingAgent")


def test_closing_and_language_layers_are_always_present() -> None:
    for persona in PERSONA_TOOLSETS:
        text = _instructions(persona)
        assert "call end_conversation to close the call" in text
        assert "call switch_spoken_language with that language code" in text


# --- Robustesse de tool_names ---------------------------------------------- #


def test_tool_names_resolves_every_shape_and_never_raises() -> None:
    def make_payment() -> None:  # resolved via __name__
        return None

    class Named:  # resolved via .name
        name = "top_up"

    class WithInfo:  # resolved via .info.name
        class info:  # noqa: N801
            name = "unblock_sim"

    class Opaque:  # MCP toolset stand-in: no resolvable name, must be skipped
        pass

    names = tool_names(
        [make_payment, Named(), WithInfo(), Opaque(), None],
        extra={"knowledge_search"},
    )
    assert {"make_payment", "top_up", "unblock_sim", "knowledge_search"} <= names
    assert tool_names(None) == frozenset()


# --- Intégrité du catalogue de domaines ------------------------------------ #


def test_every_domain_speaks_every_language() -> None:
    for domain in DOMAINS:
        assert set(domain.lines) == set(SUPPORTED_LANGUAGES)
        assert all(line.strip() for line in domain.lines.values())


def test_route_lines_match_the_shipped_v63_wording() -> None:
    assert DOMAIN_BY_KEY["billing"].lines["fr"] == (
        "Très bien, je vous mets en relation avec notre service de facturation."
    )
    assert DOMAIN_BY_KEY["technical"].lines["fr"] == (
        "Très bien, je vous mets en relation avec notre service technique."
    )
    assert DOMAIN_BY_KEY["account"].lines["fr"] == (
        "Très bien, je vous mets en relation avec notre service de gestion de compte."
    )
