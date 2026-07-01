"""Action dispatch to (mock) legacy adapters + the target-domain map (spec section 16.1).

Real Billing / OCS / NMS / Payment adapters replace dispatch() behind the same idempotency +
audit wrapper - flipping CONNECTOR_MODE, not changing callers (spec section 16.6).
"""
from __future__ import annotations

import uuid

_REFERENCE_PREFIX = {
    "EXECUTE_PAYMENT": "PAY", "PAYMENT_DEFERRAL": "DEF", "UNBLOCK_SIM": "SIM",
    "REPLACE_SIM": "SIM", "REACTIVATE_SIM": "SIM", "TOP_UP": "TOP",
    "CHANGE_PLAN": "PLN", "ACTIVATE_ROAMING": "ROAM",
}
_TARGET_DOMAIN = {
    "EXECUTE_PAYMENT": "billing", "PAYMENT_DEFERRAL": "billing", "TOP_UP": "ocs",
    "UNBLOCK_SIM": "sim", "REPLACE_SIM": "sim", "REACTIVATE_SIM": "sim",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}


def dispatch(action_type: str, payload: dict) -> str:
    """Execute the action against the legacy system (mock) and return a confirmation reference."""
    prefix = _REFERENCE_PREFIX.get(action_type, "ACT")
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def target_domain(action_type: str) -> str:
    """Map an action type to the domain whose adapter performs it."""
    return _TARGET_DOMAIN.get(action_type, "execution")