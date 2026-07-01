"""GLPI ticketing adapter implementing TicketingPort (report #3). The MCP server owns the concrete
GLPI REST client (report #4); this port impl is for domain code that depends on TicketingPort."""
from __future__ import annotations

import uuid

from domain_core.entities import Ticket
from domain_core.ports.ticketing import TicketingPort

from integration_adapters._http import get_json, post_json


class MockGlpiAdapter(TicketingPort):
    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        tid = f"GLPI-{uuid.uuid4().hex[:8].upper()}"
        return Ticket(ticket_id=tid, glpi_id=tid, subject=subject, status="new", priority=priority)

    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        return Ticket(ticket_id=ticket_id, glpi_id=ticket_id, subject="", status="new", priority="medium")


class LiveGlpiAdapter(TicketingPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        data = await post_json(self._base, "/tickets", {"subject": subject, "body": body, "priority": priority})
        return Ticket(ticket_id=data["ticket_id"], glpi_id=data.get("glpi_id"),
                      subject=subject, status=data.get("status", "new"), priority=priority)

    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        try:
            data = await get_json(self._base, f"/tickets/{ticket_id}")
        except Exception:  # noqa: BLE001
            return None
        return Ticket(ticket_id=ticket_id, glpi_id=data.get("glpi_id"),
                      subject=data.get("subject", ""), status=data.get("status", "new"),
                      priority=data.get("priority", "medium"))