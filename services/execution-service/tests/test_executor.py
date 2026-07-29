"""Offline tests for the pure dispatch/target-domain helpers (no DB).

The idempotent ledger + audit chain are integration-tested against Postgres on the developer
machine (see the persistence README)."""
from __future__ import annotations

import os

import pytest
from execution_service.executor import dispatch, target_domain

os.environ["CONNECTOR_MODE"] = "mock"
os.environ["ALLOW_MOCK_SENSITIVE"] = "1"


def test_target_domain_mapping() -> None:
    assert target_domain("EXECUTE_PAYMENT") == "billing"
    assert target_domain("PAYMENT_DEFERRAL") == "billing"
    assert target_domain("UNBLOCK_SIM") == "sim"
    assert target_domain("ACTIVATE_ROAMING") == "provisioning"
    with pytest.raises(ValueError, match="unsupported execution action: SOMETHING_ELSE"):
        target_domain("SOMETHING_ELSE")


def test_dispatch_reference_prefixes() -> None:
    assert dispatch("EXECUTE_PAYMENT", {}).startswith("MOCK-PAY-")
    assert dispatch("PAYMENT_DEFERRAL", {}).startswith("MOCK-DEF-")
    assert dispatch("UNBLOCK_SIM", {}).startswith("MOCK-SIM-")
    with pytest.raises(ValueError, match="unsupported execution action: MYSTERY"):
        dispatch("MYSTERY", {})
