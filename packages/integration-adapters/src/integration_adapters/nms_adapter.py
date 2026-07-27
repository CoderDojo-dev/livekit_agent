"""NMS/OSS adapter implementing NmsPort (report #3). Live reads outages from the OSS system."""
from __future__ import annotations

from typing import Any

from domain_core.ports.nms import NmsPort
from integration_adapters._http import get_json


class MockNmsAdapter(NmsPort):
    """Aucune source de supervision configurée -> aucune affirmation sur le réseau.

    Un mock qui répond « operational » ferait dire à l'agent que le réseau va bien alors
    que rien n'a été lu (problème #5). Même doctrine que factory.AdapterConfigError :
    on ne simule jamais silencieusement une lecture réelle.
    """

    async def get_network_status(self, area: str) -> dict[str, Any]:
        return {
            "area": area,
            "status": "unavailable",
            "verified": False,
            "outages": [],
            "reason": "mock NMS adapter: no supervision data source configured",
        }


class LiveNmsAdapter(NmsPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_network_status(self, area: str) -> dict[str, Any]:
        return await get_json(self._base, "/network-status", {"area": area})