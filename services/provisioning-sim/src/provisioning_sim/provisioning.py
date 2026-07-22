"""In-memory provisioning ledger — SIM state, plan assignments, roaming flags.

No database dependency so this simulator starts instantly. In production a carrier OCS / HLR
fulfils the same role; the provisioning adapter hides the difference.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SimRecord:
    msisdn: str
    iccid: str
    plan_code: str = "PREPAID_20GB"
    active: bool = True
    roaming_enabled: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProvisioningLedger:
    """In-memory ledger that mirrors the carrier's provisioning/HLR system."""

    def __init__(self) -> None:
        self._sims: dict[str, SimRecord] = {}

    # -- queries -----------------------------------------------------------

    def get_sim(self, msisdn: str) -> SimRecord | None:
        return self._sims.get(msisdn)

    # -- provisioning commands ---------------------------------------------

    def activate_sim(self, msisdn: str, iccid: str) -> str:
        ref = f"PRV-ACT-{uuid.uuid4().hex[:10].upper()}"
        self._sims[msisdn] = SimRecord(msisdn=msisdn, iccid=iccid)
        return ref

    def deactivate_sim(self, msisdn: str) -> str:
        if (sim := self._sims.get(msisdn)) is None:
            raise ValueError(f"msisdn {msisdn} not found")
        sim.active = False
        sim.updated_at = datetime.now(timezone.utc)
        return f"PRV-DEA-{uuid.uuid4().hex[:10].upper()}"

    def replace_sim(self, msisdn: str, new_iccid: str) -> str:
        if (sim := self._sims.get(msisdn)) is None:
            raise ValueError(f"msisdn {msisdn} not found")
        sim.iccid = new_iccid
        sim.updated_at = datetime.now(timezone.utc)
        return f"PRV-REP-{uuid.uuid4().hex[:10].upper()}"

    def change_plan(self, msisdn: str, new_plan_code: str) -> str:
        if (sim := self._sims.get(msisdn)) is None:
            raise ValueError(f"msisdn {msisdn} not found")
        sim.plan_code = new_plan_code
        sim.updated_at = datetime.now(timezone.utc)
        return f"PRV-PLN-{uuid.uuid4().hex[:10].upper()}"

    def activate_roaming(self, msisdn: str) -> str:
        if (sim := self._sims.get(msisdn)) is None:
            raise ValueError(f"msisdn {msisdn} not found")
        sim.roaming_enabled = True
        sim.updated_at = datetime.now(timezone.utc)
        return f"PRV-ROM-{uuid.uuid4().hex[:10].upper()}"
