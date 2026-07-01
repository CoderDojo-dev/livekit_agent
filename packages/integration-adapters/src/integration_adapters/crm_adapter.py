"""CRM adapter implementing CrmPort (scaffold)."""
from __future__ import annotations

from domain_core.entities import Client
from domain_core.ports.crm import CrmPort


class CrmAdapter(CrmPort):
    """Talks to the CRM / mock telco DB. Concrete queries land in Phase 4."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        raise NotImplementedError("wired in Phase 4 (Context & Identity)")

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        raise NotImplementedError("wired in Phase 4 (Context & Identity)")