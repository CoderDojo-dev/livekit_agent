"""A verdict that cannot be stored becomes an HTTP 500, and a 500 becomes a fail-closed escalation
client-side. The snapshot must therefore be JSON-serializable for every field the context can
carry - and identity_expires_at is a datetime that is only ever set after a successful
verification, which is precisely when an action is about to be authorized. That is why this defect
only ever hit the actions policy had just approved.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from policy_service.config import get_thresholds
from policy_service.schemas import PolicyContext
from policy_service.service import PolicyService

CUSTOMER_ID = "3e8fc44f-92a3-47c7-89dd-aa41d570855e"


def _verified_top_up() -> PolicyContext:
    """A context that must reach AUTHORIZED: no mandatory trigger, identity fresh and bound to the
    action customer, amount on the catalog grid."""
    return PolicyContext(
        session_id="policy-persistence-test",
        customer_id=CUSTOMER_ID,
        verified_customer_id=CUSTOMER_ID,
        action_type="TOP_UP",
        identity_verified=True,
        identity_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        amount=10.0,
    )


def test_authorized_verdict_survives_a_verification_expiry(db_session):
    result, verdict_id = PolicyService(db_session, get_thresholds()).evaluate_action(
        _verified_top_up()
    )
    assert result.verdict.upper() == "AUTHORIZED", result.justification
    assert verdict_id is not None, (
        "an authorized verdict must be persisted, not lost to a JSONB serialization error"
    )


def test_snapshot_stores_the_expiry_as_a_string(db_session):
    """The stored snapshot is what an auditor reads six months later: the expiry must be there, and
    it must be a JSON string, not a repr of a Python object."""
    from persistence.models.policy import PolicyVerdict

    _, verdict_id = PolicyService(db_session, get_thresholds()).evaluate_action(_verified_top_up())
    row = db_session.get(PolicyVerdict, verdict_id)
    assert row is not None
    stored = row.inputs_snapshot["identity_expires_at"]
    assert isinstance(stored, str), "the snapshot must round-trip through JSON"
    assert stored.startswith(str(datetime.now(UTC).year))
