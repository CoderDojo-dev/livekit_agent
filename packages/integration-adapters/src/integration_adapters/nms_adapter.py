"""NMS/OSS adapter implementing NmsPort (report #3). Live reads outages from the OSS system."""
from __future__ import annotations

from typing import Any

from domain_core.ports.nms import NmsPort
from integration_adapters._http import get_json


class MockNmsAdapter(NmsPort):
    async def get_network_status(self, area: str) -> dict[str, Any]:
        return {"area": area, "status": "operational", "outages": []}


class LiveNmsAdapter(NmsPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_network_status(self, area: str) -> dict[str, Any]:
        return await get_json(self._base, "/network-status", {"area": area})