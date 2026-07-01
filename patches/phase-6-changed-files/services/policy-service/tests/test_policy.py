"""Unit tests for the deterministic engine + mandatory audit (offline, no FastAPI/network)."""
from __future__ import annotations

from audit_trail import AuditLedger

from policy_service.config import PolicyThresholds
from policy_service.schemas import PolicyContext
from policy_service.service import PolicyService

THRESHOLDS = PolicyThresholds(_env_file=None)


def _service() -> PolicyService:
    return PolicyService(AuditLedger(), THRESHOLDS)


def _ctx(**over) -> PolicyContext:
    base = dict(action_type="PAYMENT_DEFERRAL", identity_verified=True, account_age_days=400)
    base.update(over)
    return PolicyContext(**base)


def test_clean_deferral_is_authorized() -> None:
    result = _service().evaluate_action(_ctx(unpaid_amount=42.5))
    assert result.verdict == "authorized"
    assert result.rule_id == "DEF_OK"


def test_vip_short_circuits_to_escalate() -> None:
    result = _service().evaluate_action(_ctx(is_vip=True))
    assert result.verdict == "escalate"
    assert result.rule_id == "ESC_VIP"


def test_fraud_short_circuits_first() -> None:
    # fraud beats everything, even a young account that would otherwise be REFUSED
    result = _service().evaluate_action(_ctx(fraud_suspected=True, account_age_days=10))
    assert (result.verdict, result.rule_id) == ("escalate", "ESC_FRAUD")


def test_deferral_below_min_age_is_refused() -> None:
    result = _service().evaluate_action(_ctx(account_age_days=30))
    assert (result.verdict, result.rule_id) == ("refused", "DEF_MIN_AGE")


def test_deferral_high_unpaid_escalates_for_review() -> None:
    result = _service().evaluate_action(_ctx(unpaid_amount=500.0))
    assert (result.verdict, result.rule_id) == ("escalate", "DEF_UNPAID_REVIEW")


def test_payment_without_confirmation_is_refused() -> None:
    result = _service().evaluate_action(
        PolicyContext(action_type="EXECUTE_PAYMENT", identity_verified=True, payment_confirmed=False)
    )
    assert (result.verdict, result.rule_id) == ("refused", "PAY_NO_CONFIRMATION")


def test_payment_above_cap_escalates() -> None:
    result = _service().evaluate_action(
        PolicyContext(
            action_type="EXECUTE_PAYMENT", identity_verified=True, payment_confirmed=True, amount=5000.0
        )
    )
    assert (result.verdict, result.rule_id) == ("escalate", "PAY_ABOVE_CAP")


def test_sim_without_identity_escalates() -> None:
    result = _service().evaluate_action(
        PolicyContext(action_type="UNBLOCK_SIM", identity_verified=False)
    )
    assert result.verdict == "escalate"  # IDENTITY_STEP_UP or SIM_IDENTITY_REQUIRED


def test_every_verdict_is_audited_and_chain_is_intact() -> None:
    service = _service()
    service.evaluate_action(_ctx())                 # authorized (a no-op still logs)
    service.evaluate_action(_ctx(is_vip=True))      # escalate
    service.evaluate_response("sess-1", "your account 100021456 is fine")  # refused (PII)
    assert len(service.ledger.entries) == 3
    assert service.ledger.verify() is True


def test_outbound_pii_is_refused() -> None:
    result = _service().evaluate_response("unknown", "your id is 100021456789")
    assert (result.verdict, result.rule_id) == ("refused", "OUT_PII")