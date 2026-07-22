"""Provisioning / SIM lifecycle port — activates, blocks, replaces SIMs and changes plans."""
from __future__ import annotations

from typing import Protocol

from domain_core.value_objects import IdempotencyKey


class ProvisioningPort(Protocol):
    """One interface for all provisioning operations (Blueprint ADR 3.4, CDC 5.4)."""

    async def activate_sim(self, msisdn: str, sim_iccid: str, key: IdempotencyKey) -> str:
        """Activate a fresh SIM for an MSISDN. Returns a provisioning reference."""
        ...

    async def deactivate_sim(self, msisdn: str, key: IdempotencyKey) -> str:
        """Deactivate (lock) the SIM associated with an MSISDN. Returns a reference."""
        ...

    async def replace_sim(self, msisdn: str, new_sim_iccid: str, key: IdempotencyKey) -> str:
        """Replace the SIM on an MSISDN. Returns a reference."""
        ...

    async def change_plan(self, msisdn: str, new_plan_code: str, key: IdempotencyKey) -> str:
        """Change the active plan for an MSISDN. Returns a reference."""
        ...

    async def activate_roaming(self, msisdn: str, key: IdempotencyKey) -> str:
        """Enable roaming on an MSISDN. Returns a reference."""
        ...
