"""Account-services tool facades: plan query/change, recharge, roaming (Phase 5/7)."""
from __future__ import annotations


async def top_up_credit(customer_id: str, amount: str) -> dict:
    """Sensitive: Decision -> Policy -> Execution (CDC 5.7). Wired in Phase 7."""
    raise NotImplementedError("wired in Phase 7")


async def activate_roaming(customer_id: str) -> dict:
    """Sensitive: Decision -> Policy -> Execution (CDC 5.8). Wired in Phase 7."""
    raise NotImplementedError("wired in Phase 7")