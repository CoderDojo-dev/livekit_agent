"""The one and only path from a sensitive tool to an action (cookbook section 8).

  1. assemble context from the verified session (canonical UUIDs included),
  2. Decision proposes a candidate + confidence (low -> escalate, never force),
  3. Policy issues the binding verdict, PERSISTED with an id (audited server-side),
  4. only AUTHORIZED reaches Execution - dispatched idempotently against the verdict id, audited.
REFUSED / ESCALATE short-circuit into a standard outcome the caller can be told plainly.
"""
from __future__ import annotations

import logging

from livekit.agents import RunContext

from clients.decision_client import get_decision_client
from clients.execution_client import get_execution_client
from clients.policy_client import get_policy_client
from config import get_settings
from tools import outcomes

logger = logging.getLogger(__name__)

_FRUSTRATION_STREAK = 3  # consecutive negative turns -> frustration (sentiment, Phase 8)


def _build_context(run_context: RunContext, action_type: str, payload: dict) -> dict:
    user_data = run_context.session.userdata
    customer = user_data.customer_context
    context = {
        "session_id": user_data.session_id,
        "customer_id": customer.customer_id if customer else None,
        "subscription_id": getattr(customer, "subscription_id", None) if customer else None,
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
    """Run Decision -> Policy -> Execution for ``action_type`` and return a standard outcome."""
    context = _build_context(run_context, action_type, payload)

    decision = await get_decision_client().recommend(action_type, context)
    if decision["confidence"] < get_settings().decision_confidence_threshold:
        logger.info("decision below threshold for %s -> escalate", action_type)
        return outcomes.escalate("DECISION_LOW_CONFIDENCE", decision["rationale"])

    verdict = await get_policy_client().evaluate_action(context)
    if verdict["verdict"] == "refused":
        return outcomes.refused(verdict["rule_id"], verdict["justification"])
    if verdict["verdict"] == "escalate":
        return outcomes.escalate(verdict["rule_id"], verdict["justification"])

    verdict_id = verdict.get("verdict_id")
    if not verdict_id:  # AUTHORIZED must carry a persisted verdict id; never execute without one
        return outcomes.escalate("POLICY_NO_VERDICT_ID", "authorized verdict missing its persisted id")

    # AUTHORIZED -> execute idempotently against the verdict that authorized it.
    user_data = run_context.session.userdata
    idempotency_key = user_data.new_idempotency_key(action_type)
    return await get_execution_client().execute(
        idempotency_key,
        action_type,
        context["session_id"],
        payload,
        policy_verdict_id=verdict_id,
        customer_id=context["customer_id"],
        subscription_id=context["subscription_id"],
    )