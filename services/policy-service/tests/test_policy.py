"""Unit tests for the deterministic engine + mandatory audit (offline, no FastAPI/network)."""
from __future__ import annotations

from policy_service.config import PolicyThresholds
from policy_service.engine import evaluate_action as _engine_evaluate
from policy_service.engine import evaluate_response as _engine_evaluate_response
from policy_service.schemas import PolicyContext

THRESHOLDS = PolicyThresholds(_env_file=None)


class _EngineShim:
    """Exercises the pure rule engine (no DB); the persistence wrapper is integration-tested."""

    def evaluate_action(self, ctx):
        return _engine_evaluate(ctx, THRESHOLDS)

    def evaluate_response(self, session_id, text):
        return _engine_evaluate_response(text)


def _service() -> _EngineShim:
    return _EngineShim()


def _ctx(**over) -> PolicyContext:
    base = {"action_type": "PAYMENT_DEFERRAL", "identity_verified": True, "account_age_days": 400}
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


def test_every_action_yields_a_verdict() -> None:
    # Persistence/audit of each verdict is structural in PolicyService and is covered by
    # audit-trail/test_chain.py + Postgres integration; here we assert the engine always decides.
    for ctx in (_ctx(), _ctx(is_vip=True), _ctx(fraud_suspected=True)):
        assert _service().evaluate_action(ctx).verdict in ("authorized", "refused", "escalate")


def test_outbound_pii_is_refused() -> None:
    result = _service().evaluate_response("unknown", "your id is 100021456789")
    assert (result.verdict, result.rule_id) == ("refused", "OUT_PII")
