"""Network supervision (NMS) adapter implementing NmsPort (scaffold)."""
from __future__ import annotations

from typing import Any

from domain_core.ports.nms import NmsPort


class NmsAdapter(NmsPort):
    """Talks to the NMS. Concrete I/O lands in Phase 8/9."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def get_network_status(self, area: str) -> dict[str, Any]:
        raise NotImplementedError("wired in Phase 8")