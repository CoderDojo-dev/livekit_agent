"""Mock GLPI client (in-memory ticket store). A real GLPI REST adapter replaces this without
changing the tools. Tickets become Postgres/GLPI-backed in the persistence phase.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ticket:
    """A GLPI ticket."""

    ticket_id: str
    customer_id: str
    subject: str
    description: str
    status: str            # "new" | "resolved"
    resolution: str | None = None


class MockGlpiClient:
    """In-memory GLPI ticket lifecycle."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0

    def create(self, customer_id: str, subject: str, description: str) -> Ticket:
        self._counter += 1
        ticket_id = f"GLPI-{self._counter:05d}"
        ticket = Ticket(ticket_id, customer_id, subject, description, status="new")
        self._tickets[ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "resolved"
        ticket.resolution = resolution
        return ticket

    def list_for(self, customer_id: str) -> list[Ticket]:
        return [t for t in self._tickets.values() if t.customer_id == customer_id]