"""Port to the provisioning / SIM lifecycle system (Blueprint section 8).

Keyed on ``customer_id``, not on an MSISDN: every identifier that flows through the platform
(policy verdicts, execution ledger, audit) is the customer UUID, and the provisioning system is
the component that knows which line that customer holds. Passing an MSISDN here would force every
caller to resolve one first, and getting that wrong silently provisions the wrong line.

Unblock and reactivate are separate operations even though both end with an active line: they
start from different states (BLOCKED vs SUSPENDED) and a system of record must reject the wrong
transition rather than force it.

Every write carries an IdempotencyKey, because a retried call on a voice line must never
provision twice.
"""
from __future__ import annotations

from typing import Protocol

from domain_core.value_objects import IdempotencyKey


class ProvisioningPort(Protocol):
    """SIM lifecycle and subscription changes."""

    async def unblock_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        """Unblock a BLOCKED line. Returns a reference."""
        ...

    async def reactivate_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        """Reactivate a SUSPENDED line. Returns a reference."""
        ...

    async def replace_sim(self, customer_id: str, sim_type: str, key: IdempotencyKey) -> str:
        """Order a replacement SIM (physical/esim). Returns a reference."""
        ...

    async def change_plan(self, customer_id: str, plan_code: str, key: IdempotencyKey) -> str:
        """Move the subscription to ``plan_code``. Returns a reference."""
        ...

    async def set_roaming(self, customer_id: str, enable: bool, key: IdempotencyKey) -> str:
        """Enable or disable roaming. Returns a reference."""
        ...
