"""Provisioning / SIM lifecycle adapter implementing ProvisioningPort.

Live mode talks to the provisioning system over REST (in dev, the provisioning-sim service, which
mutates the real subscription/SIM tables). Every request carries the idempotency key, so a retry
provisions once - the previous implementation accepted the key and dropped it, which meant a
retried SIM order could be executed twice.

Mock is reachable only when CONNECTOR_MODE=mock, for offline unit tests.
"""
from __future__ import annotations

from domain_core.ports.provisioning import ProvisioningPort
from domain_core.value_objects import IdempotencyKey
from integration_adapters._http import post_json


class MockProvisioningAdapter(ProvisioningPort):
    async def unblock_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-UNB-{key.value[:10].upper()}"

    async def reactivate_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-REA-{key.value[:10].upper()}"

    async def replace_sim(self, customer_id: str, sim_type: str, key: IdempotencyKey) -> str:
        return f"MOCK-SIM-REP-{key.value[:10].upper()}"

    async def change_plan(self, customer_id: str, plan_code: str, key: IdempotencyKey) -> str:
        return f"MOCK-PLN-{key.value[:10].upper()}"

    async def set_roaming(self, customer_id: str, enable: bool, key: IdempotencyKey) -> str:
        return f"MOCK-ROM-{key.value[:10].upper()}"


class LiveProvisioningAdapter(ProvisioningPort):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def unblock_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/unblock", {
            "customer_id": customer_id, "idempotency_key": key.value,
        })
        return resp.get("reference", "")

    async def reactivate_sim(self, customer_id: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/reactivate", {
            "customer_id": customer_id, "idempotency_key": key.value,
        })
        return resp.get("reference", "")

    async def replace_sim(self, customer_id: str, sim_type: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/replace", {
            "customer_id": customer_id, "sim_type": sim_type or "physical",
            "idempotency_key": key.value,
        })
        return resp.get("reference", "")

    async def change_plan(self, customer_id: str, plan_code: str, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/change-plan", {
            "customer_id": customer_id, "plan_code": plan_code, "idempotency_key": key.value,
        })
        return resp.get("reference", "")

    async def set_roaming(self, customer_id: str, enable: bool, key: IdempotencyKey) -> str:
        resp = await post_json(self._base_url, "/sim/roaming", {
            "customer_id": customer_id, "enable": bool(enable), "idempotency_key": key.value,
        })
        return resp.get("reference", "")
