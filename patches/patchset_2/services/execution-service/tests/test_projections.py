"""Offline tests for the pure projection mapping (no DB). The DB writes are integration-tested."""
from __future__ import annotations

from execution_service.projections import installment_amount, projection_kind, sim_case_action


def test_projection_kind() -> None:
    assert projection_kind("EXECUTE_PAYMENT") == "payment"
    assert projection_kind("PAYMENT_DEFERRAL") == "payment_plan"
    assert projection_kind("TOP_UP") == "recharge"
    assert projection_kind("UNBLOCK_SIM") == "sim_case"
    assert projection_kind("REACTIVATE_SIM") == "sim_case"
    assert projection_kind("CHANGE_PLAN") == "provisioning"
    assert projection_kind("ACTIVATE_ROAMING") == "provisioning"
    assert projection_kind("SEND_SMS") is None


def test_sim_case_action() -> None:
    assert sim_case_action("UNBLOCK_SIM") == "UNBLOCK"
    assert sim_case_action("REACTIVATE_SIM") == "REACTIVATE"
    assert sim_case_action("EXECUTE_PAYMENT") is None


def test_installment_amount() -> None:
    assert installment_amount(120, 3) == 40.0
    assert installment_amount(73.9, 1) == 73.9
    assert installment_amount(100, 0) == 100.0  # guarded to >=1 installment