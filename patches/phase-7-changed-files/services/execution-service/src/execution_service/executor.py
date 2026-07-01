"""Action dispatch to (mock) legacy adapters. Phase 7 simulates success and returns a reference.

Real Billing / OCS / NMS / Payment adapters (the domain ports) replace dispatch() without
changing callers — the idempotency + audit wrapper around it stays identical.
"""
from __future__ import annotations

import uuid

_REFERENCE_PREFIX = {
    "EXECUTE_PAYMENT": "PAY",
    "PAYMENT_DEFERRAL": "DEF",
    "UNBLOCK_SIM": "SIM",
    "REPLACE_SIM": "SIM",
    "REACTIVATE_SIM": "SIM",
    "TOP_UP": "TOP",
    "CHANGE_PLAN": "PLN",
    "ACTIVATE_ROAMING": "ROAM",
}


def dispatch(action_type: str, payload: dict) -> str:
    """Execute the action against the legacy system (mock) and return a confirmation reference."""
    prefix = _REFERENCE_PREFIX.get(action_type, "ACT")
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"