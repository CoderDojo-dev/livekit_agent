"""Port to the ticketing system (GLPI) (Blueprint section 7.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.entities import Ticket


class TicketingPort(ABC):
    """Create and look up support tickets."""

    @abstractmethod
    async def create_ticket(self, subject: str, body: str, priority: str) -> Ticket:
        """Create a ticket and return it with its GLPI id."""

    @abstractmethod
    async def get_ticket_status(self, ticket_id: str) -> Ticket | None:
        """Return the current ticket or None if not found."""