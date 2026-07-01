"""Offline tests for the pure dispatch/target-domain helpers (no DB).

The idempotent ledger + audit chain are integration-tested against Postgres on the developer
machine (see the persistence README)."""
from __future__ import annotations

from execution_service.executor import dispatch, target_domain


def test_target_domain_mapping() -> None:
    assert target_domain("EXECUTE_PAYMENT") == "billing"
    assert target_domain("PAYMENT_DEFERRAL") == "billing"
    assert target_domain("UNBLOCK_SIM") == "sim"
    assert target_domain("ACTIVATE_ROAMING") == "provisioning"
    assert target_domain("SOMETHING_ELSE") == "execution"


def test_dispatch_reference_prefixes() -> None:
    assert dispatch("EXECUTE_PAYMENT", {}).startswith("PAY-")
    assert dispatch("PAYMENT_DEFERRAL", {}).startswith("DEF-")
    assert dispatch("UNBLOCK_SIM", {}).startswith("SIM-")
    assert dispatch("MYSTERY", {}).startswith("ACT-")