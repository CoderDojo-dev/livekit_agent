"""Action dispatch (report #10): mock by default, routed to the real adapters when CONNECTOR_MODE=live.

Mock keeps the deterministic prefixed reference so existing behaviour/tests are unchanged. Live
routes billing/OCS/payment actions through integration-adapters (which fall back to mock if their
URL is unset). Actions without a live port yet (SIM / plan / roaming) return a synthesized
reference and are flagged for binding.
"""
from __future__ import annotations

import logging
import os
import uuid
from decimal import Decimal

from integration_adapters.config import is_live

logger = logging.getLogger(__name__)

_REFERENCE_PREFIX = {
    "EXECUTE_PAYMENT": "PAY", "PAYMENT_DEFERRAL": "DEF", "UNBLOCK_SIM": "SIM",
    "REPLACE_SIM": "SIM", "REACTIVATE_SIM": "SIM", "TOP_UP": "TOP",
    "CHANGE_PLAN": "PLN", "ACTIVATE_ROAMING": "ROAM",
}
_MONEY_ACTIONS = frozenset({"EXECUTE_PAYMENT", "TOP_UP", "PAYMENT_DEFERRAL"})
_TARGET_DOMAIN = {
    "EXECUTE_PAYMENT": "billing", "PAYMENT_DEFERRAL": "billing", "TOP_UP": "ocs",
    "UNBLOCK_SIM": "sim", "REPLACE_SIM": "sim", "REACTIVATE_SIM": "sim",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}

SUPPORTED_ACTIONS = frozenset(_REFERENCE_PREFIX)


def _require_supported_action(action_type: str) -> None:
    if action_type not in SUPPORTED_ACTIONS:
        raise ValueError(f"unsupported execution action: {action_type}")


def _mock_reference(action_type: str) -> str:
    _require_supported_action(action_type)
    return f"MOCK-{_REFERENCE_PREFIX[action_type]}-{uuid.uuid4().hex[:10].upper()}"


def dispatch(action_type: str, payload: dict, *, customer_id: str | None = None,
             idempotency_key: str | None = None) -> str:
    """Execute the action against the legacy system and return a confirmation reference."""
    _require_supported_action(action_type)
    if not is_live():
        if action_type in _MONEY_ACTIONS and os.getenv("ALLOW_MOCK_SENSITIVE", "0") != "1":
            raise RuntimeError(
                f"Refusing to {action_type} in mock mode without ALLOW_MOCK_SENSITIVE=1"
            )
        return _mock_reference(action_type)
    return _dispatch_live(action_type, payload, customer_id, idempotency_key)


def _dispatch_live(action_type: str, payload: dict, customer_id: str | None, idempotency_key: str | None) -> str:
    import asyncio

    from integration_adapters import (
        get_balance_adapter,
        get_billing_adapter,
        get_provisioning_adapter,
    )

    from domain_core.value_objects import IdempotencyKey, Money

    key = IdempotencyKey(idempotency_key or uuid.uuid4().hex)
    amount = Money(Decimal(str(payload.get("amount") or 0)))
    try:
        if action_type == "EXECUTE_PAYMENT":
            return asyncio.run(get_billing_adapter().charge(customer_id or "", amount, key))
        if action_type == "PAYMENT_DEFERRAL":
            asyncio.run(get_billing_adapter().grant_deferral(customer_id or "", int(payload.get("requested_days") or 0), key))
            return f"DEF-{key.value[:10].upper()}"
        if action_type == "TOP_UP":
            return asyncio.run(get_balance_adapter().top_up(customer_id or "", amount, key))
        if action_type == "CHANGE_PLAN":
            return asyncio.run(get_provisioning_adapter().change_plan(
                customer_id or "", str(payload.get("plan_code", "")), key,
            ))
        if action_type == "ACTIVATE_ROAMING":
            return asyncio.run(get_provisioning_adapter().set_roaming(
                customer_id or "", bool(payload.get("enable", True)), key,
            ))
        # UNBLOCK and REACTIVATE are distinct transitions (BLOCKED vs SUSPENDED); the provisioning
        # system validates the starting state rather than forcing the line active.
        if action_type == "UNBLOCK_SIM":
            return asyncio.run(get_provisioning_adapter().unblock_sim(customer_id or "", key))
        if action_type == "REACTIVATE_SIM":
            return asyncio.run(get_provisioning_adapter().reactivate_sim(customer_id or "", key))
        if action_type == "REPLACE_SIM":
            return asyncio.run(get_provisioning_adapter().replace_sim(
                customer_id or "", str(payload.get("sim_type", "physical")), key,
            ))
    except Exception as exc:
        logger.error("live dispatch failed for %s: %s", action_type, exc)
        raise
    # In live mode an unmapped action must fail honestly, not return a synthesized reference that
    # implies a real operation happened.
    raise NotImplementedError(f"no live adapter mapped for action {action_type!r}")


def target_domain(action_type: str) -> str:
    """Map an action type to the domain whose adapter performs it."""
    _require_supported_action(action_type)
    return _TARGET_DOMAIN[action_type]
