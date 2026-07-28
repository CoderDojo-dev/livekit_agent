"""Agent-side ticketing facades (identity-injecting wrappers over the ticketing-glpi MCP tools).

Why these exist instead of exposing the raw MCP tools to the model: the caller's identity
(customer_id, subscription_id) lives in the session's CustomerContext, resolved from the MSISDN
at call start. The MCP server runs in a separate process and cannot see it, so if the model were
asked to pass customer_id it would guess or omit it - which is exactly why every mirrored ticket
had a NULL customer_id. These wrappers inject the VERIFIED ids from session context, so the model
only supplies the human content (subject, description) and the platform supplies identity.

They also give the agent the proactive behaviour the product needs: check_customer_tickets lets
a persona see a caller's open tickets and tell them where their problem stands, in French.
"""
from __future__ import annotations

import json
import logging
import os

from livekit.agents import RunContext, function_tool

_TICKETING_HTTP_URL = os.getenv(
    "TICKETING_HTTP_URL",
    os.getenv("TICKETING_MCP_URL", "http://localhost:8202/mcp").replace("/mcp", ""),
)
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
logger = logging.getLogger(__name__)


def _customer(context: RunContext):
    """The caller's verified context snapshot, or None when the line is unresolved."""
    user_data = getattr(context.session, "userdata", None)
    return getattr(user_data, "customer_context", None) if user_data else None


class TicketingUnavailable(RuntimeError):
    """The ticketing service could not be reached or errored. Surfaced as an honest failure."""


def _extract_result(result: object, tool: str) -> dict | list | None:
    """Pull a tool's return value out of an MCP CallToolResult.

    Prefers ``structuredContent`` (MCP 2025-06+), but falls back to the JSON text carried in
    ``content`` - which is what our FastMCP server actually populates (``structuredContent`` comes
    back ``None``). Reading only ``structuredContent`` was the ticketing bug: every call returned
    ``None`` and the wrappers reported "unavailable" even though GLPI had created the ticket.

    FastMCP wraps list/scalar returns under ``{"result": ...}``; we unwrap that consistently in both
    paths, so a dict return (e.g. ``{"ticket_id": ...}``) passes through untouched while a list
    return (``lookup_tickets``) comes back as a list whether or not it was wrapped.
    """
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured

    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            logger.warning("ticketing tool %s returned non-JSON content: %.200s", tool, text)
            return None
        return parsed.get("result", parsed) if isinstance(parsed, dict) else parsed

    return None


async def _mcp_call(tool: str, arguments: dict) -> dict | list | None:
    """Invoke a ticketing-glpi MCP tool over streamable HTTP and return its structured result.

    Raises TicketingUnavailable on any transport/protocol failure so the caller-facing wrappers
    can tell the truth ("I can't reach the ticketing system right now") instead of letting a raw
    exception crash the tool call and leave the agent silent. There is NO fake fallback: a real
    failure is reported as a failure.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    url = os.getenv("TICKETING_MCP_URL", "http://localhost:8202/mcp")
    headers = {"X-API-Key": _INTERNAL_API_KEY} if _INTERNAL_API_KEY else {}
    try:
        from observability_kit.telemetry import inject_trace_context
        headers = inject_trace_context(headers)
    except Exception:
        pass

    try:
        async with streamablehttp_client(url, headers=headers) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
                if getattr(result, "isError", False):
                    raise TicketingUnavailable(f"ticketing tool {tool!r} returned an error")
                return _extract_result(result, tool)
    except TicketingUnavailable:
        raise
    except Exception as exc:  # connection refused, timeout, protocol error
        logger.error("ticketing MCP call %s failed: %s", tool, exc)
        raise TicketingUnavailable(str(exc)) from exc


# What every wrapper returns when ticketing is unreachable. The message tells the model to be
# honest with the caller and never invent a ticket or a status.
def _unavailable(extra: dict | None = None) -> dict:
    payload = {
        "outcome": "unavailable",
        "message": (
            "The ticketing system is unavailable right now. Tell the caller honestly, in their "
            "language, that you cannot access or record tickets at the moment and will try later. "
            "Do NOT invent a ticket, a reference, or a status."
        ),
    }
    if extra:
        payload.update(extra)
    return payload


# --- v61 : vocabulaire d'etats et bornes partagees -------------------------------
_OPEN_STATES = {"open", "in_progress", "pending"}
_CLOSED_STATES = {"resolved", "closed"}
_MAX_LISTED = 10

_STOP_WORDS = {
    "le", "la", "les", "de", "des", "du", "un", "une", "mon", "ma", "mes",
    "pour", "avec", "depuis", "est", "sur", "dans", "pas", "plus", "tres",
    "cette", "cet", "chez", "mais", "donc", "vous", "nous",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _keywords(text: str) -> set[str]:
    """Mots signifiants d'un sujet de ticket (sans regex, sans dependance)."""
    cleaned = _norm(text)
    for ch in ",.;:!?'()[]-":
        cleaned = cleaned.replace(ch, " ")
    return {w for w in cleaned.split() if len(w) > 3 and w not in _STOP_WORDS}


def _same_problem(subject: str, category: str, ticket: dict) -> bool:
    """Vrai quand un ticket existant couvre plausiblement le meme probleme.

    Deux signaux volontairement simples et explicables : meme categorie, ou au moins deux
    mots signifiants communs dans le sujet. Aucun seuil flou, aucun modele : un humain peut
    rejouer la decision a la main.
    """
    if category and ticket.get("category") and category == ticket.get("category"):
        return True
    new_words = _keywords(subject)
    old_words = _keywords(ticket.get("subject") or "")
    return bool(new_words and old_words and len(new_words & old_words) >= 2)


async def _list_tickets(context: RunContext) -> tuple[list[dict], dict | None]:
    """(tickets, echec). `echec` non None quand la ligne ou le ticketing est indisponible.

    Point d'entree unique de toute lecture : garantit que chaque outil voit exactement le
    meme perimetre, celui du client de la session.
    """
    customer = _customer(context)
    if customer is None:
        return [], {"outcome": "unavailable", "tickets": [],
                    "message": "No active line is resolved for this caller."}
    try:
        result = await _mcp_call("lookup_tickets", {
            "customer_id": customer.customer_id,
            "requester_glpi_id": getattr(customer, "glpi_user_id", None),
        })
    except TicketingUnavailable:
        return [], _unavailable({"tickets": []})
    return (result if isinstance(result, list) else []), None


async def _owned(context: RunContext, ticket_id: str) -> bool | None:
    """True/False quand la propriete est determinable, None quand le ticketing est injoignable."""
    tickets, failure = await _list_tickets(context)
    if failure is not None:
        return None
    return any(t.get("ticket_id") == ticket_id for t in tickets)


def _refused_foreign() -> dict:
    return {
        "outcome": "refused",
        "message": (
            "That ticket reference does not belong to this caller. Do NOT disclose anything "
            "about it and do NOT modify it: ask the caller to confirm their own reference."
        ),
    }


@function_tool()
async def create_support_ticket(
    context: RunContext,
    subject: str,
    description: str,
    category: str = "other",
    priority: str = "",
    confirm_new: bool = False,
) -> dict:
    """Open a support ticket for an issue that could not be solved on the call.

    Identity (customer + subscription) is taken from the verified session context, not from you.
    You supply only the human content.

    Args:
        subject: Short ticket subject in the caller's language.
        description: What needs follow-up.
        category: network_complaint / formal_complaint / technical / billing / other.
        priority: low / medium / high / urgent (optional; leave empty if unsure).
        confirm_new: Leave false. Set true ONLY after the caller explicitly asked for a
            SECOND ticket while an open one already covers the same problem.
    """
    customer = _customer(context)
    if customer is None:
        return {"outcome": "unavailable",
                "message": "No active line is resolved for this caller; cannot open a ticket."}

    # Garde anti-doublon : la verification que le modele "pourrait" faire est faite ICI, donc
    # elle a toujours lieu. Si la lecture echoue, on cree quand meme : jamais de regression
    # sur le chemin qui fonctionne aujourd'hui.
    if not confirm_new:
        existing, failure = await _list_tickets(context)
        if failure is None:
            duplicates = [t for t in existing
                          if t.get("status") in _OPEN_STATES
                          and _same_problem(subject, category, t)]
            if duplicates:
                logger.info("ticket duplicate guard: %d open ticket(s) already cover %r",
                            len(duplicates), subject)
                return {
                    "outcome": "duplicate_candidate",
                    "tickets": duplicates[:3],
                    "message": (
                        "An OPEN ticket already covers this problem. Tell the caller its "
                        "reference and current status, then ask whether they want you to keep "
                        "following the existing ticket (do nothing further) or open a separate "
                        "one. ONLY if they ask for a new one, call create_support_ticket again "
                        "with confirm_new set to true. Never create a duplicate on your own."
                    ),
                }

    language = getattr(customer, "preferred_language", "fr") or "fr"
    try:
        result = await _mcp_call("create_ticket", {
            "customer_id": customer.customer_id,
            "subject": subject,
            "description": description,
            "language": language,
            "category": category,
            "subscription_id": customer.subscription_id or "",
            "priority": priority or "",
            "requester_glpi_id": getattr(customer, "glpi_user_id", None),
        })
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def check_customer_tickets(context: RunContext) -> dict:
    """List the caller's existing tickets so you can tell them where their problem stands.

    Use this proactively when a caller mentions a problem: if an open ticket already covers it,
    reassure them it is being handled; if one is resolved, tell them the good news. Identity is
    taken from the verified session context.
    """
    tickets, failure = await _list_tickets(context)
    if failure is not None:
        return failure

    open_tickets = [t for t in tickets if t.get("status") in _OPEN_STATES]
    resolved = [t for t in tickets if t.get("status") in _CLOSED_STATES]
    return {
        "outcome": "listed",
        "total": len(tickets),
        "open_count": len(open_tickets),
        "resolved_count": len(resolved),
        "tickets": tickets[:_MAX_LISTED],
        "message": (
            "Summarize for the caller in their language: if an open ticket matches their "
            "problem, give its reference and tell them it is being handled; if a matching "
            "ticket is resolved, tell them the good news. Never invent a ticket that is not "
            "in this list."
        ),
    }


@function_tool()
async def get_ticket_state(context: RunContext, ticket_id: str) -> dict:
    """Check the current status of one ticket by its reference (e.g. 'GLPI-42')."""
    owned = await _owned(context, ticket_id)
    if owned is None:
        return _unavailable()
    if owned is False:
        return _refused_foreign()

    try:
        result = await _mcp_call("get_ticket_status", {"ticket_id": ticket_id})
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def mark_ticket_resolved(
    context: RunContext,
    resolution: str,
    ticket_id: str = "",
) -> dict:
    """Resolve a ticket when the caller's issue was solved during the call.

    Args:
        resolution: A short note on how it was solved.
        ticket_id: The ticket reference (e.g. 'GLPI-42'). LEAVE EMPTY when the caller simply
            says their problem is solved without giving a reference: the caller's single open
            ticket is then resolved, and if several are open you are asked which one.
    """
    if not ticket_id:
        tickets, failure = await _list_tickets(context)
        if failure is not None:
            return failure
        open_tickets = [t for t in tickets if t.get("status") in _OPEN_STATES]
        if not open_tickets:
            return {
                "outcome": "nothing_to_resolve",
                "message": (
                    "This caller has no open ticket. Say so plainly and warmly acknowledge "
                    "that their problem is solved. Do NOT invent a ticket or a reference."
                ),
            }
        if len(open_tickets) > 1:
            return {
                "outcome": "needs_selection",
                "tickets": open_tickets[:5],
                "message": (
                    "Several open tickets could match. Read their subjects to the caller, ask "
                    "which one is solved, then call mark_ticket_resolved again with that "
                    "ticket_id. Resolve NOTHING before they answer."
                ),
            }
        ticket_id = open_tickets[0]["ticket_id"]
    else:
        owned = await _owned(context, ticket_id)
        if owned is None:
            return _unavailable()
        if owned is False:
            return _refused_foreign()

    try:
        result = await _mcp_call("resolve_ticket",
                                 {"ticket_id": ticket_id, "resolution": resolution})
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def update_support_ticket(
    context: RunContext,
    ticket_id: str,
    subject: str = "",
    description: str = "",
    priority: str = "",
    category: str = "",
) -> dict:
    """Update an existing ticket's subject, description, priority, or category."""
    owned = await _owned(context, ticket_id)
    if owned is None:
        return _unavailable()
    if owned is False:
        return _refused_foreign()

    try:
        result = await _mcp_call("update_ticket", {
            "ticket_id": ticket_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "category": category,
        })
    except TicketingUnavailable:
        return _unavailable()
    return result or _unavailable()  # type: ignore[return-value]


@function_tool()
async def delete_support_ticket(context: RunContext, ticket_id: str, reason: str = "") -> dict:
    """Withdraw a ticket that was opened by mistake (caller's own, still-open tickets only).

    A resolved or closed ticket is part of the customer's history and is never deleted.

    Args:
        ticket_id: The ticket reference to withdraw (e.g. 'GLPI-42').
        reason: Why the caller wants it withdrawn.
    """
    owned = await _owned(context, ticket_id)
    if owned is None:
        return _unavailable()
    if owned is False:
        return _refused_foreign()

    try:
        state = await _mcp_call("get_ticket_status", {"ticket_id": ticket_id})
    except TicketingUnavailable:
        return _unavailable()
    status = (state or {}).get("status")
    if status not in _OPEN_STATES:
        return {
            "outcome": "refused",
            "ticket_id": ticket_id,
            "status": status,
            "message": (
                "Only an OPEN ticket can be withdrawn. Explain to the caller that a ticket "
                "already resolved or closed stays in their history."
            ),
        }

    try:
        result = await _mcp_call("delete_ticket", {"ticket_id": ticket_id})
    except TicketingUnavailable:
        return _unavailable()
    if not (result or {}).get("deleted"):
        return {"outcome": "failed",
                "message": "The ticket could not be withdrawn. Tell the caller honestly."}
    logger.info("ticket %s withdrawn (reason=%r)", ticket_id, reason)
    return {"outcome": "deleted", "ticket_id": ticket_id,
            "message": "Confirm to the caller that the ticket was withdrawn."}
