"""The one and only path from a sensitive tool to an action (cookbook section 8).

Every sensitive tool calls execute_guarded_action, so a tool author CANNOT skip Policy:
  1. assemble context from the verified session (no re-fetch of identity here),
  2. Decision proposes a candidate + confidence (low -> escalate, never force),
  3. Policy issues the binding three-way verdict (audited inside the policy-service),
  4. only AUTHORIZED proceeds to Execution (wired in Phase 7); REFUSED/ESCALATE short-circuit.
"""
from __future__ import annotations

import logging

from livekit.agents import RunContext

from clients.decision_client import get_decision_client
from clients.policy_client import get_policy_client
from config import get_settings

logger = logging.getLogger(__name__)

_FRUSTRATION_STREAK = 3  # consecutive negative turns -> frustration (sentiment lands in Phase 8)


def _build_context(run_context: RunContext, action_type: str, payload: dict) -> dict:
    user_data = run_context.session.userdata
    customer = user_data.customer_context
    context = {
        "session_id": user_data.session_id,
        "action_type": action_type,
        "is_vip": customer.is_vip if customer else False,
        "fraud_suspected": getattr(customer, "fraud_suspected", False) if customer else False,
        "frustration": user_data.consecutive_negative_turns >= _FRUSTRATION_STREAK,
        "identity_verified": user_data.identity_verified,
        "clarification_attempts": user_data.clarification_attempts,
        "identity_attempts": user_data.identity_attempts,
        "account_age_days": customer.account_age_days if customer else 0,
    }
    context.update(payload)
    return context


async def execute_guarded_action(run_context: RunContext, action_type: str, payload: dict) -> dict:
    """Run Decision -> Policy for ``action_type`` and return a small structured outcome."""
    context = _build_context(run_context, action_type, payload)

    decision = await get_decision_client().recommend(action_type, context)
    if decision["confidence"] < get_settings().decision_confidence_threshold:
        logger.info("decision below threshold for %s -> escalate", action_type)
        return {"outcome": "escalate", "rule_id": "DECISION_LOW_CONFIDENCE", "reason": decision["rationale"]}

    verdict = await get_policy_client().evaluate_action(context)
    if verdict["verdict"] == "refused":
        return {"outcome": "refused", "rule_id": verdict["rule_id"], "reason": verdict["justification"]}
    if verdict["verdict"] == "escalate":
        return {"outcome": "escalate", "rule_id": verdict["rule_id"], "reason": verdict["justification"]}

    # AUTHORIZED — Execution is wired in Phase 7 (idempotent dispatch + result audit).
    return {
        "outcome": "authorized",
        "rule_id": verdict["rule_id"],
        "action_type": action_type,
        "pending": "execution_phase_7",
    }