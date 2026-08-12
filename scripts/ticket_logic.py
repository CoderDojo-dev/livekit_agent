"""Shared test doubles and helpers for ticketing v61 validation checks.

Not imported by any production code. Kept separate so the checks script stays
readable — each check is one assertion, not twenty lines of setup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeCustomer:
    customer_id: str = "cust-001"
    subscription_id: str = "sub-001"
    preferred_language: str = "fr"
    glpi_user_id: int | None = 5


@dataclass
class FakeUserData:
    customer_context: FakeCustomer | None = None
    language: str = "fr"


class FakeSession:
    userdata: FakeUserData


_NOT_GIVEN = object()


class FakeContext:
    session: FakeSession

    def __init__(self, customer: FakeCustomer | None = _NOT_GIVEN) -> None:
        self.session = FakeSession()
        if customer is _NOT_GIVEN:
            customer = FakeCustomer()
        self.session.userdata = FakeUserData(customer_context=customer)


def ctx_with_customer() -> FakeContext:
    """Shorthand: a context with a valid default customer."""
    return FakeContext(customer=FakeCustomer())


def ctx_no_customer() -> FakeContext:
    """Shorthand: a context with no resolved customer line."""
    return FakeContext(customer=None)


class FakeToolResult:
    """Mimics MCP CallToolResult — content list with JSON text blocks."""

    def __init__(self, data: Any, is_error: bool = False) -> None:
        import json
        self.content = [FakeTextBlock(json.dumps({"result": data}))]
        self.isError = is_error
        self.structuredContent = None  # MCP 2025-06+; our FastMCP never sets it


class FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.text = text


# --- Shared test tickets -------------------------------------------------

TICKET_A_NETWORK = {
    "ticket_id": "GLPI-1",
    "subject": "Pas de connexion dans le centre ville",
    "status": "open",
    "category": "network_complaint",
    "priority": "high",
}
TICKET_A_SAME = {
    "ticket_id": "GLPI-1",
    "subject": "Probleme de connexion internet",
    "status": "open",
    "category": "network_complaint",
}
TICKET_B_BILLING = {
    "ticket_id": "GLPI-2",
    "subject": "Facture trop elevee",
    "status": "in_progress",
    "category": "billing",
}
TICKET_C_RESOLVED = {
    "ticket_id": "GLPI-3",
    "subject": "Carte SIM bloquee",
    "status": "resolved",
    "category": "technical",
}
TICKET_D_CLOSED = {
    "ticket_id": "GLPI-4",
    "subject": "Probleme de debit",
    "status": "closed",
    "category": "network_complaint",
}
TICKET_E_OTHER_CUSTOMER = {
    "ticket_id": "GLPI-99",
    "subject": "Secret d'un autre client",
    "status": "open",
    "category": "other",
}

ALL_TICKETS = [
    TICKET_A_NETWORK,
    TICKET_B_BILLING,
    TICKET_C_RESOLVED,
    TICKET_D_CLOSED,
]
