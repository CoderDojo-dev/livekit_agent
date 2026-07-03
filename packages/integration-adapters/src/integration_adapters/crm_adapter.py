"""CRM adapter implementing CrmPort (report #3). In mock mode CRM reads come from Postgres
(context-service); this adapter is the *live* CRM binding."""
from __future__ import annotations

from domain_core.entities import Client
from domain_core.ports.crm import CrmPort
from integration_adapters._http import get_json


def _to_client(data: dict) -> Client:
    return Client(
        customer_id=data["customer_id"], full_name=data.get("full_name", ""),
        msisdn=data.get("msisdn", ""), subscription_type=data.get("subscription_type", ""),
    )


class MockCrmAdapter(CrmPort):
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        return None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        return None


class LiveCrmAdapter(CrmPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        try:
            return _to_client(await get_json(self._base, "/clients", {"msisdn": msisdn}))
        except Exception:
            return None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        try:
            return _to_client(await get_json(self._base, f"/clients/{customer_id}"))
        except Exception:
            return None