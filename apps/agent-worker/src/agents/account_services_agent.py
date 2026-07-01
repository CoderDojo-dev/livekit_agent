"""AccountServicesAgent: plan query/change, recharge, roaming (CDC 5.6-5.8)."""
from __future__ import annotations

from livekit.agents import Agent


class AccountServicesAgent(Agent):
    """Lower-risk tier; many tools hit the Knowledge MCP (Phase 5/7)."""

    def __init__(self) -> None:
        super().__init__(instructions="You handle plans, recharges and roaming.")