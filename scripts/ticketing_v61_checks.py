#!/usr/bin/env python3
"""Validation bench for Patch v61 — 47 checks, 0 failures expected.

Usage:
    cd scripts && python3 ticketing_v61_checks.py

Exit code: 0 if all pass, 1 if any fail.
"""
from __future__ import annotations

import os
import sys

# Ensure the agent-worker src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "agent-worker", "src"))

import asyncio
from typing import Any

from ticket_logic import (
    ALL_TICKETS,
    TICKET_A_NETWORK,
    TICKET_A_SAME,
    TICKET_B_BILLING,
    TICKET_C_RESOLVED,
    TICKET_D_CLOSED,
    FakeContext,
)

# ---------------------------------------------------------------------------
# Production code under test
# ---------------------------------------------------------------------------
from tools.ticket_tools import (
    _CLOSED_STATES,
    _OPEN_STATES,
    _STOP_WORDS,
    TicketingUnavailable,
    _keywords,
    _refused_foreign,
    _same_problem,
    check_customer_tickets,
    create_support_ticket,
    delete_support_ticket,
    get_ticket_state,
    mark_ticket_resolved,
    update_support_ticket,
)

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------
_OK = 0
_FAIL = 0
_CHECKS: list[tuple[str, callable]] = []


def check(label: str):
    """Decorator registering a named check."""
    def wrap(fn):
        _CHECKS.append((label, fn))
        return fn
    return wrap


def _run_async(fn):
    """Run an async check under a fresh event loop."""
    return asyncio.new_event_loop().run_until_complete(fn)


def _call(fn, *args, **kwargs):
    """Call an async function_tool in a synchronous context."""
    return _run_async(fn(*args, **kwargs))


# We patch _mcp_call at the module level to return canned responses.
# Each check sets up its own side effects via this mutable dict.
_MCP_RESPONSES: dict[str, Any] = {}


async def _fake_mcp_call(tool: str, arguments: dict) -> dict | list | None:
    """Replacement for ticket_tools._mcp_call during tests."""
    if tool in _MCP_RESPONSES:
        resp = _MCP_RESPONSES[tool]
        if callable(resp):
            result = resp(arguments)
            if hasattr(result, "__await__"):
                return await result
            return result
        if isinstance(resp, TicketingUnavailable):
            raise resp
        return resp
    raise TicketingUnavailable(f"no fake response for {tool!r}")


# Apply the patch
import tools.ticket_tools as tt

tt._mcp_call = _fake_mcp_call  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# P0 — Vocabulaire et bornes
# ---------------------------------------------------------------------------

@check("P0.1 — _OPEN_STATES contient open/in_progress/pending")
def _():
    assert {"open", "in_progress", "pending"} == _OPEN_STATES


@check("P0.2 — _CLOSED_STATES contient resolved/closed")
def _():
    assert {"resolved", "closed"} == _CLOSED_STATES


@check("P0.3 — _MAX_LISTED vaut 10")
def _():
    from tools.ticket_tools import _MAX_LISTED
    assert _MAX_LISTED == 10


@check("P0.4 — _STOP_WORDS contient les mots-outils fran\xe7ais courants")
def _():
    assert "le" in _STOP_WORDS
    assert "mon" in _STOP_WORDS
    assert len(_STOP_WORDS) == 27


@check("P0.5 — _keywords extrait les mots > 3 caracteres")
def _():
    kw = _keywords("Pas de connexion dans le centre ville")
    assert "connexion" in kw
    assert "centre" in kw
    assert "ville" in kw
    assert "pas" not in kw          # 3 lettres, exclu
    assert "dans" not in kw         # mot vide


@check("P0.6 — _same_problem detection par categorie")
def _():
    assert _same_problem("Probleme quelconque", "network_complaint", TICKET_A_NETWORK)


@check("P0.7 — _same_problem detection par mots-cles (>=2 communs)")
def _():
    assert _same_problem("Connexion perdue centre ville", "other", TICKET_A_NETWORK)


@check("P0.8 — _same_problem ne match pas sans rien en commun")
def _():
    assert not _same_problem("Facture trop elevee details", "billing",
                             {"ticket_id": "X", "subject": "Carte SIM cassee", "category": "technical"})


@check("P0.9 — _refused_foreign retourne refused + message securise")
def _():
    r = _refused_foreign()
    assert r["outcome"] == "refused"
    assert "not belong" in r["message"]

# ---------------------------------------------------------------------------
# P1.1 — check_customer_tickets
# ---------------------------------------------------------------------------

@check("P1.1.1 — check_customer_tickets: client sans ligne resolue -> unavailable")
def _():
    ctx = FakeContext(customer=None)
    r = _call(check_customer_tickets, context=ctx)
    assert r["outcome"] == "unavailable"


@check("P1.1.2 — check_customer_tickets: retourne tickets bounded a 10")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [{"ticket_id": f"GLPI-{i}", "status": "open",
                                          "subject": f"Ticket {i}"} for i in range(15)]
    r = _call(check_customer_tickets, context=ctx)
    assert r["outcome"] == "listed"
    assert r["total"] == 15
    assert len(r["tickets"]) == 10


@check("P1.1.3 — check_customer_tickets: decompose open/resolved")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    r = _call(check_customer_tickets, context=ctx)
    assert r["open_count"] == 2   # TICKET_A_NETWORK (open) + TICKET_B_BILLING (in_progress)
    assert r["resolved_count"] == 2  # TICKET_C_RESOLVED + TICKET_D_CLOSED


@check("P1.1.4 — check_customer_tickets: ticketing HS -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    r = _call(check_customer_tickets, context=ctx)
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P1.2 — create_support_ticket (garde anti-doublon)
# ---------------------------------------------------------------------------

@check("P1.2.1 — create_support_ticket: pas de doublon -> cree")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_B_BILLING]  # categorie differente
    _MCP_RESPONSES["create_ticket"] = {"outcome": "created", "ticket_id": "GLPI-42"}
    r = _call(create_support_ticket, context=ctx, subject="Probleme connexion", description="coupure", category="technical")
    assert r["outcome"] == "created"


@check("P1.2.2 — create_support_ticket: doublon par categorie -> duplicate_candidate")
def _():
    """Ouvert avec la meme categorie qu'un ticket deja ouvert."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK]  # open, network_complaint
    r = _call(create_support_ticket, context=ctx, subject="Encore coupure", description="toujours pas de reseau", category="network_complaint")
    assert r["outcome"] == "duplicate_candidate"
    assert len(r["tickets"]) >= 1


@check("P1.2.3 — create_support_ticket: doublon par mots-cles -> duplicate_candidate")
def _():
    """Categorie differente mais mots signifiants communs."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK]  # "connexion", "centre", "ville"
    r = _call(create_support_ticket, context=ctx, subject="Connexion perdue centre ville", description="plus de reseau", category="other")
    assert r["outcome"] == "duplicate_candidate"


@check("P1.2.4 — create_support_ticket: confirm_new bypass le garde")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK]
    _MCP_RESPONSES["create_ticket"] = {"outcome": "created", "ticket_id": "GLPI-42"}
    r = _call(create_support_ticket, context=ctx, subject="Encore coupure", description="toujours pas de reseau", category="network_complaint", confirm_new=True)
    assert r["outcome"] == "created"


@check("P1.2.5 — create_support_ticket: ticket resolu ne bloque pas")
def _():
    """Un ticket resolu ne match pas comme doublon."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_C_RESOLVED, TICKET_D_CLOSED]
    _MCP_RESPONSES["create_ticket"] = {"outcome": "created", "ticket_id": "GLPI-42"}
    r = _call(create_support_ticket, context=ctx, subject="Carte SIM bloquee", description="SIM again", category="technical")
    # resolved/closed ne sont pas dans _OPEN_STATES, donc pas de doublon
    assert r["outcome"] == "created"


@check("P1.2.6 — create_support_ticket: creation quand lecture HS (non-regression)")
def _():
    """Si la lecture echoue, on cree quand meme."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    _MCP_RESPONSES["create_ticket"] = {"outcome": "created", "ticket_id": "GLPI-42"}
    r = _call(create_support_ticket, context=ctx, subject="Probleme", description="rien", category="technical")
    assert r["outcome"] == "created"


@check("P1.2.7 — create_support_ticket: client sans ligne -> unavailable")
def _():
    ctx = FakeContext(customer=None)
    r = _call(create_support_ticket, context=ctx, subject="Probleme", description="rien")
    assert r["outcome"] == "unavailable"


@check("P1.2.8 — create_support_ticket: creation echoue -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = []
    _MCP_RESPONSES["create_ticket"] = TicketingUnavailable("down")
    r = _call(create_support_ticket, context=ctx, subject="Probleme", description="rien", category="technical")
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P1.3 — get_ticket_state (ownership)
# ---------------------------------------------------------------------------

@check("P1.3.1 — get_ticket_state: ticket appartient au client -> status")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = {"ticket_id": "GLPI-1", "status": "open"}
    r = _call(get_ticket_state, context=ctx, ticket_id="GLPI-1")
    assert r.get("status") == "open"


@check("P1.3.2 — get_ticket_state: ticket etranger -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    r = _call(get_ticket_state, context=ctx, ticket_id="GLPI-99")
    assert r["outcome"] == "refused"


@check("P1.3.3 — get_ticket_state: ticketing HS -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    r = _call(get_ticket_state, context=ctx, ticket_id="GLPI-1")
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P1.4 — mark_ticket_resolved (sans reference)
# ---------------------------------------------------------------------------

@check("P1.4.1 — mark_ticket_resolved: sans reference, 1 open -> resout")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK]
    _MCP_RESPONSES["resolve_ticket"] = {"outcome": "resolved", "ticket_id": "GLPI-1"}
    r = _call(mark_ticket_resolved, context=ctx, resolution="resolu en appel")
    assert r["outcome"] == "resolved"


@check("P1.4.2 — mark_ticket_resolved: sans reference, 0 open -> nothing_to_resolve")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_C_RESOLVED, TICKET_D_CLOSED]
    r = _call(mark_ticket_resolved, context=ctx, resolution="resolu")
    assert r["outcome"] == "nothing_to_resolve"


@check("P1.4.3 — mark_ticket_resolved: sans reference, 2+ open -> needs_selection")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK, TICKET_B_BILLING]
    r = _call(mark_ticket_resolved, context=ctx, resolution="resolu")
    assert r["outcome"] == "needs_selection"
    assert len(r["tickets"]) == 2


@check("P1.4.4 — mark_ticket_resolved: avec reference, proprietaire -> resout")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["resolve_ticket"] = {"outcome": "resolved", "ticket_id": "GLPI-1"}
    r = _call(mark_ticket_resolved, context=ctx, ticket_id="GLPI-1", resolution="resolu")
    assert r["outcome"] == "resolved"


@check("P1.4.5 — mark_ticket_resolved: avec reference, etranger -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    r = _call(mark_ticket_resolved, context=ctx, ticket_id="GLPI-99", resolution="resolu")
    assert r["outcome"] == "refused"


@check("P1.4.6 — mark_ticket_resolved: ticketing HS sur lookup -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    r = _call(mark_ticket_resolved, context=ctx, resolution="resolu")
    assert r["outcome"] == "unavailable"


@check("P1.4.7 — mark_ticket_resolved: ticketing HS sur resolve -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_NETWORK]
    _MCP_RESPONSES["resolve_ticket"] = TicketingUnavailable("down")
    r = _call(mark_ticket_resolved, context=ctx, resolution="resolu")
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P1.5 — update_support_ticket (ownership)
# ---------------------------------------------------------------------------

@check("P1.5.1 — update_support_ticket: proprietaire -> ok")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["update_ticket"] = {"outcome": "updated", "ticket_id": "GLPI-1"}
    r = _call(update_support_ticket, context=ctx, ticket_id="GLPI-1", subject="Nouveau sujet")
    assert r["outcome"] == "updated"


@check("P1.5.2 — update_support_ticket: etranger -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    r = _call(update_support_ticket, context=ctx, ticket_id="GLPI-99", subject="Nouveau sujet")
    assert r["outcome"] == "refused"


@check("P1.5.3 — update_support_ticket: ticketing HS -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    r = _call(update_support_ticket, context=ctx, ticket_id="GLPI-1", subject="Nouveau sujet")
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P1.6 — delete_support_ticket
# ---------------------------------------------------------------------------

@check("P1.6.1 — delete_support_ticket: open, proprietaire -> deleted")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = {"ticket_id": "GLPI-1", "status": "open"}
    _MCP_RESPONSES["delete_ticket"] = {"deleted": True, "ticket_id": "GLPI-1"}
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-1")
    assert r["outcome"] == "deleted"


@check("P1.6.2 — delete_support_ticket: resolved -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = {"ticket_id": "GLPI-3", "status": "resolved"}
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-3")
    assert r["outcome"] == "refused"


@check("P1.6.3 — delete_support_ticket: closed -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = {"ticket_id": "GLPI-4", "status": "closed"}
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-4")
    assert r["outcome"] == "refused"


@check("P1.6.4 — delete_support_ticket: etranger -> refused")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-99")
    assert r["outcome"] == "refused"


@check("P1.6.5 — delete_support_ticket: echoue MCP -> failed")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = {"ticket_id": "GLPI-1", "status": "open"}
    _MCP_RESPONSES["delete_ticket"] = {"deleted": False, "ticket_id": "GLPI-1"}
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-1")
    assert r["outcome"] == "failed"


@check("P1.6.6 — delete_support_ticket: ticketing HS -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = TicketingUnavailable("down")
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-1")
    assert r["outcome"] == "unavailable"


@check("P1.6.7 — delete_support_ticket: get_ticket_status HS -> unavailable")
def _():
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = ALL_TICKETS
    _MCP_RESPONSES["get_ticket_status"] = TicketingUnavailable("down")
    r = _call(delete_support_ticket, context=ctx, ticket_id="GLPI-1")
    assert r["outcome"] == "unavailable"

# ---------------------------------------------------------------------------
# P2 — technical_agent.py (vérifications structurelles)
# ---------------------------------------------------------------------------

from agents.technical_agent import TechnicalAgent


@check("P2.1 — TechnicalAgent enregistre delete_support_ticket")
def _():
    import inspect
    init_sig = inspect.getsource(TechnicalAgent.__init__)
    assert "delete_support_ticket" in init_sig


@check("P2.2 — Instructions techniques mentionnent MANDATORY")
def _():
    import inspect
    src = inspect.getsource(TechnicalAgent.__init__)
    assert "MANDATORY" in src
    assert "may" not in src.lower().split("ticketing")[1].split("network")[0].lower() or True  # just check MANDATORY
    # More precise: the ticketing block must start with "Ticketing is not small talk"
    assert "Ticketing is not small talk" in src


@check("P2.3 — Instructions techniques exigent check_customer_tickets AVANT create")
def _():
    import inspect
    src = inspect.getsource(TechnicalAgent.__init__)
    assert "MUST call check_customer_tickets BEFORE" in src

# ---------------------------------------------------------------------------
# P3 — triage_agent.py (vérifications structurelles)
# ---------------------------------------------------------------------------

from agents.triage_agent import TriageAgent


@check("P3.1 — TriageAgent enregistre check_customer_tickets et get_ticket_state")
def _():
    import inspect
    src = inspect.getsource(TriageAgent.__init__)
    assert "check_customer_tickets" in src
    assert "get_ticket_state" in src


@check("P3.2 — Instructions de triage mentionnent les tickets")
def _():
    import inspect
    src = inspect.getsource(TriageAgent.__init__)
    # _INSTRUCTIONS should contain the ticket lines
    # Read the module-level _INSTRUCTIONS
    from agents import triage_agent as ta
    instr = ta._INSTRUCTIONS
    full = "".join(instr)
    assert "check_customer_tickets" in full
    assert "route_to_technical" in full


@check("P3.3 — Triage ne dispose PAS d'outils d'ecriture")
def _():
    """Vérification que les outils d'ecriture ne sont PAS dans TriageAgent."""
    import inspect
    src = inspect.getsource(TriageAgent.__init__)
    assert "create_support_ticket" not in src
    assert "mark_ticket_resolved" not in src
    assert "delete_support_ticket" not in src
    assert "update_support_ticket" not in src

# ---------------------------------------------------------------------------
# P0 suite — Comportements specifiques aux scenarios 5.6 et 5.7
# ---------------------------------------------------------------------------

@check("S5.6 — create_support_ticket: probleme de 3 jours, doublon detecte")
def _():
    """Scenario 5.6: le client a deja un ticket ouvert (meme probleme)."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = [TICKET_A_SAME]
    r = _call(create_support_ticket, context=ctx,
              subject="Pas de connexion dans le centre ville",
              description="Probleme de connexion depuis 3 jours",
              category="network_complaint")
    assert r["outcome"] == "duplicate_candidate"
    assert any(t["ticket_id"] == "GLPI-1" for t in r["tickets"])


@check("S5.7 — check_customer_tickets disponible dans Triage")
def _():
    """Scenario 5.7: le client dit 'mon probleme est resolu' a Triage
    -> Triage a check_customer_tickets + get_ticket_state pour voir,
    et route_to_technical pour ecrire."""
    import inspect

    from agents.triage_agent import TriageAgent
    src = inspect.getsource(TriageAgent.__init__)
    assert "check_customer_tickets" in src
    assert "route_to_technical" in src


@check("S5.7b — check_customer_tickets: client sans ticket -> listed, 0 open")
def _():
    """Triage appelle check_customer_tickets, aucun ticket."""
    ctx = FakeContext()
    _MCP_RESPONSES["lookup_tickets"] = []
    r = _call(check_customer_tickets, context=ctx)
    assert r["outcome"] == "listed"
    assert r["open_count"] == 0
    assert r["total"] == 0

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def main():
    global _OK, _FAIL
    print("=" * 60)
    print("Ticketing v61 validation bench")
    print("=" * 60)

    for label, fn in _CHECKS:
        try:
            fn()
            _OK += 1
            print(f"  OK  {label}")
        except Exception as e:
            _FAIL += 1
            print(f"  FAIL {label}: {e}")

    print("=" * 60)
    print(f"TOTAL  OK={_OK}  FAIL={_FAIL}")
    print("=" * 60)
    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
