"""Port to the CRM system of record (Blueprint section 7.2)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain_core.entities import Client


class CrmPort(ABC):
    """Resolve and read customer profiles from the CRM."""

    @abstractmethod
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        """Return the client owning ``msisdn`` or None if unknown."""

    @abstractmethod
    async def get_client_by_id(self, customer_id: str) -> Client | None:
        """Return the client with ``customer_id`` or None if unknown."""