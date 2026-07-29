"""Derive persona instructions from the tools a persona actually owns.

The routing mandate used to be a frozen block injected into every persona, so it
could order BillingAgent to call route_to_billing -- a tool BillingAgent does not
have. Here the mandate is a PROJECTION of the registered tool set: an instruction
citing an unavailable tool is not merely discouraged, it is unrepresentable.

Everything in this module is pure (no session, no network, no SDK state), so the
whole instruction layer is unit-testable without a LiveKit room or a TTS key.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Sequence

from agents.domains import DOMAINS

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Tool names with cross-persona meaning
# --------------------------------------------------------------------------- #

CLARIFICATION_TOOL = "request_clarification"
ESCALATION_TOOL = "escalate_to_manager"
KNOWLEDGE_TOOL = "knowledge_search"
HUMAN_TRANSFER_TOOL = "transfer_to_human"
END_CALL_TOOL = "end_conversation"
LANGUAGE_SWITCH_TOOL = "switch_spoken_language"

# Every tool name the validator knows how to look for. Kept as an explicit
# catalog rather than introspected at import time, so this module stays free of
# import cycles and of side effects. scripts/persona_contract_checks.py asserts
# that the catalog covers every @function_tool in the tree, which turns a
# forgotten entry into a CI failure instead of a silent validation gap.
KNOWN_TOOL_VOCABULARY: frozenset[str] = frozenset(
    {
        # routing / flow
        "route_to_billing",
        "route_to_account_services",
        "route_to_technical",
        "request_clarification",
        "escalate_to_manager",
        "transfer_to_human",
        "end_conversation",
        "switch_spoken_language",
        "knowledge_search",
        # billing
        "get_invoice_summary",
        "get_balance_summary",
        "make_payment",
        "request_payment_deferral",
        "confirm_payment",
        "decline_callback",
        # account services
        "get_plan_details",
        "change_plan",
        "top_up",
        "toggle_roaming",
        "record_callback",
        "record_consent",
        "record_sim_replacement_details",
        # technical
        "unblock_sim",
        "unblock_sim_pin",
        "cancel_sim_replacement",
        "replace_sim",
        "diagnose_data_issue",
        "check_network_status",
        # identity
        "verify_with_known_element",
        # ticketing
        "create_support_ticket",
        "check_customer_tickets",
        "get_ticket_state",
        "mark_ticket_resolved",
        "update_support_ticket",
        "delete_support_ticket",
    }
)


def tool_names(tools: Sequence | None, extra: Iterable[str] = ()) -> frozenset[str]:
    """Names of the given tools, plus explicitly declared remote capabilities.

    A @function_tool keeps its ``__name__``; some SDK wrappers expose ``name`` or
    ``info.name`` instead, so all three are tried in order. An object with no
    resolvable name -- typically an MCP toolset, whose tool list only exists once
    the server has been reached -- is skipped and must be declared through
    ``extra``. A name that fails to resolve can only make a mandate line absent;
    it can never raise.
    """
    names: set[str] = {name for name in extra if isinstance(name, str) and name}
    for tool in tools or ():
        candidate: str | None = None
        for attribute in ("name", "__name__"):
            value = getattr(tool, attribute, None)
            if isinstance(value, str) and value:
                candidate = value
                break
        if candidate is None:
            value = getattr(getattr(tool, "info", None), "name", None)
            if isinstance(value, str) and value:
                candidate = value
        if candidate is not None:
            names.add(candidate)
    return frozenset(names)


# --------------------------------------------------------------------------- #
# Shared instruction layers (moved VERBATIM from base_agent.py)
# --------------------------------------------------------------------------- #

# Shared closing protocol appended to every persona's instructions so ending a
# call behaves identically no matter which specialist is active.
CLOSING_PROTOCOL = (
    "\n\nEnding the call: when the caller's need is fully handled -- information "
    "delivered, a ticket created, an issue escalated, a callback scheduled, or "
    "the caller signals they are finished -- first ask, in the caller's language, "
    "whether there is anything else you can help with. If they need more, "
    "continue normally. Only once the caller clearly has nothing else, or clearly "
    "wants to leave or says goodbye, call end_conversation to close the call. "
    "Judge this from the caller's intent, not from a fixed list of keywords. "
    "Never call end_conversation while the caller still needs help, and never end "
    "without first confirming there is nothing else. When you call "
    "end_conversation, do not also speak a goodbye yourself -- the tool delivers "
    "the farewell."
)

# Resolves the contradiction between the per-persona "Never switch to another
# language" lock and the auto-injected switch_spoken_language tool: the lock
# still prevents self-initiated drift, but an EXPLICIT caller request is allowed.
LANGUAGE_SWITCH_POLICY = (
    "\n\nLanguage: keep speaking your fixed language and never drift on your own. "
    "The only exception overriding any 'never switch language' rule above: if the "
    "caller EXPLICITLY asks to continue in French, Arabic, or English, call "
    "switch_spoken_language with that language code, then continue in it."
)

# Phase 8.1: knowledge-answer abstention rule. Now appended AUTOMATICALLY to the
# personas that declare the knowledge_search capability, instead of being
# concatenated by hand in each persona (which was one more place to forget).
KNOWLEDGE_ABSTENTION_RULE = (
    "When you use the knowledge_search tool, GROUND your answer strictly in the returned passages: "
    "never guess or add facts they do not contain, and if they do not directly answer the question, "
    "reply in French: \"Je n'ai pas cette information.\"\n"
    "But you are TALKING on a phone call, not reading a document. Never read a passage aloud "
    "verbatim, and never use numbered or bulleted lists (no \"1- 2- 3-\"), headings, or long "
    "paragraphs. Instead, answer the way a real advisor speaks out loud: ONE or two short, natural "
    "sentences carrying only the essential point the caller needs, in their language. Do not say "
    "source codes, file names, or URLs aloud. Then, in the same breath, briefly offer more if they "
    "want it (e.g. whether they'd like the exact steps or more detail). ONLY if the caller asks for "
    "more do you give further detail or the concrete steps -- and even then keep it spoken: short, "
    "one point at a time, conversational, never a read-out list or a wall of text."
)

TTS_LANGUAGE_REMINDER = (
    "\n\nIMPORTANT: You MUST speak ONLY in the language already specified above. Never switch."
)


# --------------------------------------------------------------------------- #
# Derived routing mandate
# --------------------------------------------------------------------------- #


def routing_mandate(available: frozenset[str]) -> str:
    """Routing mandate citing ONLY tools present in ``available``.

    A persona that cannot route a domain away necessarily owns it, so the very
    absence that used to produce a phantom tool call now produces an explicit
    ownership statement. A persona without escalate_to_manager is the terminal
    escalation point (the manager): it claims no domain and is pointed at
    transfer_to_human instead.
    """
    terminal = ESCALATION_TOOL not in available
    parts: list[str] = ["\n\nRouting mandate (you MUST follow this):\n"]

    for domain in DOMAINS:
        if domain.route_tool in available:
            parts.append(
                f"- If {domain.route_condition}, "
                f"call {domain.route_tool} immediately.\n"
            )
        elif not terminal:
            parts.append(
                f"- {domain.own_topics} are YOUR OWN responsibility: handle them with "
                "your own tools. Never route them away and never tell the caller you "
                "are transferring them for this.\n"
            )

    if CLARIFICATION_TOOL in available:
        parts.append(f"- If the request is ambiguous, call {CLARIFICATION_TOOL}.\n")
    else:
        parts.append(
            "- If the request is ambiguous, ask the caller ONE short question yourself, "
            "then continue.\n"
        )

    if terminal:
        parts.append(
            "- You are the FINAL escalation point: never send the caller to another "
            f"department or another number yourself. Use {HUMAN_TRANSFER_TOOL}, or the "
            "callback it schedules, or track the issue with a ticket."
        )
    else:
        parts.append(
            "- NEVER tell the caller to call a different department or number yourself. "
            f"Use the route_* tool. If none of the above fits, call {ESCALATION_TOOL}.\n"
            "- The route_* tools transfer the caller to the right specialist; after calling "
            "one you will NOT speak again, so do not also say goodbye yourself."
        )

    return "".join(parts)


def build_persona_instructions(
    core: str,
    available: frozenset[str],
    *,
    tts_provided: bool = True,
) -> str:
    """Assemble the full instruction block for a persona.

    Layer order reproduces the pre-refactor layout exactly
    (core [+ knowledge rule] + mandate + closing + language [+ TTS lock]), so a
    persona whose mandate was already correct receives an identical prompt.
    """
    head = core
    if KNOWLEDGE_TOOL in available:
        head = core + "\n\n" + KNOWLEDGE_ABSTENTION_RULE
    parts: list[str] = [head, routing_mandate(available), CLOSING_PROTOCOL, LANGUAGE_SWITCH_POLICY]
    if tts_provided:
        parts.append(TTS_LANGUAGE_REMINDER)
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Invariant enforcement
# --------------------------------------------------------------------------- #

STRICT_ENV_VAR = "STRICT_PERSONA_CONTRACT"


def instruction_violations(instructions: str, available: frozenset[str]) -> list[str]:
    """Known tool names cited by the instructions but not registered on the persona.

    Catches the generated layers AND the hand-written persona core, which is the
    other place where a stale tool name can hide.
    """
    return sorted(
        name
        for name in KNOWN_TOOL_VOCABULARY
        if name not in available and name in instructions
    )


def enforce_contract(persona: str, instructions: str, available: frozenset[str]) -> None:
    """Raise in CI, log loudly in production. A live call is never sacrificed."""
    violations = instruction_violations(instructions, available)
    if not violations:
        return
    detail = f"{persona} is instructed to use unavailable tools: {violations}"
    if os.getenv(STRICT_ENV_VAR) == "1":
        raise RuntimeError(detail)
    logger.error("persona contract violation - %s", detail)
