"""GLPI ticketing adapter implementing TicketingPort (scaffold)."""
from __future__ import annotations

from domain_core.entities import Ticket
from domain_core.ports.ticketing import TicketingPort


class GlpiAdapter(TicketingPort):
    """Talks to GLPI. Concrete I/O lands in Phase 9 (exposed via the MCP server)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        raise NotImplementedError("wired in Phase 9")

    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        raise NotImplementedError("wired in Phase 9")