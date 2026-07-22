"""Provisioning adapter: mock (default) / live (CONNECTOR_MODE=live + PROVISIONING_ADAPTER_URL).

Implements the ProvisioningPort protocol.
"""
from __future__ import annotations

import uuid

from domain_core.value_objects import IdempotencyKey
from integration_adapters._http import post_json


class MockProvisioningAdapter:
    """Deterministic mock that returns prefixed references without side effects."""

    @staticmethod
    async def activate_sim(msisdn: str, sim_iccid: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-ACT-{msisdn}-{key.value[:10].upper()}"

    @staticmethod
    async def deactivate_sim(msisdn: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-DEA-{msisdn}-{key.value[:10].upper()}"

    @staticmethod
    async def replace_sim(msisdn: str, new_sim_iccid: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-REP-{msisdn}-{key.value[:10].upper()}"

    @staticmethod
    async def change_plan(msisdn: str, new_plan_code: str, key: IdempotencyKey) -> str:
        return f"MOCK-PLN-{msisdn}-{key.value[:10].upper()}"

    @staticmethod
    async def activate_roaming(msisdn: str, key: IdempotencyKey) -> str:
        return f"MOCK-ROM-{msisdn}-{key.value[:10].upper()}"


class LiveProvisioningAdapter:
    """Live HTTP adapter that talks to the carrier's provisioning system (or our simulator)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def activate_sim(self, msisdn: str, sim_iccid: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/activate", {"msisdn": msisdn, "iccid": sim_iccid})
        return resp["reference"]

    async def deactivate_sim(self, msisdn: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/deactivate", {"msisdn": msisdn})
        return resp["reference"]

    async def replace_sim(self, msisdn: str, new_sim_iccid: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/replace", {"msisdn": msisdn, "new_iccid": new_sim_iccid})
        return resp["reference"]

    async def change_plan(self, msisdn: str, new_plan_code: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/change-plan", {"msisdn": msisdn, "new_plan_code": new_plan_code})
        return resp["reference"]

    async def activate_roaming(self, msisdn: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/activate-roaming", {"msisdn": msisdn})
        return resp["reference"]
