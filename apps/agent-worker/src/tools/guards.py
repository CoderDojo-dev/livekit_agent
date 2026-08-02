"""Reusable, persisted sensitive-action identity preconditions."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from clients.context_client import get_context_client
from livekit.agents import RunContext
from tasks.identity_verification_task import IdentityVerificationTask
from tools.voice_flow import active_persona_tts

logger = logging.getLogger(__name__)

# Timeout hierarchy (invariant): VERIFY_CALL_TIMEOUT_S < TASK_DEADLINE_S < GATE_TIMEOUT_S.
# The gate waits slightly longer than the whole identity task so a task-level
# timeout is reported as such instead of being swallowed by the outer deadline.
GATE_TIMEOUT_S = 60.0


def identity_is_fresh(user_data) -> bool:
    """Require fresh verification bound to the current customer."""
    customer = getattr(user_data, "customer_context", None)
    expires_at = getattr(user_data, "expires_at", None)

    return bool(
        customer
        and getattr(user_data, "identity_verified", False)
        and getattr(user_data, "verified_customer_id", None)
        == customer.customer_id
        and expires_at
        and expires_at > datetime.now(UTC)
    )


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def ensure_identity_verified(context: RunContext) -> bool:
    """Verify CIN once per customer/session and reuse it until expiration."""
    user_data = context.session.userdata

    if identity_is_fresh(user_data):
        return True

    customer = user_data.customer_context
    if customer is None:
        logger.info("identity gate: caller not resolved")
        return False

    async def verify(customer_id: str, provided_value: str) -> bool:
        result = await get_context_client().verify_identity(
            customer_id,
            provided_value,
            user_data.session_id,
        )

        user_data.verification_session_id = result.get(
            "verification_session_id"
        )
        user_data.verification_level = result.get("verification_level")
        user_data.verification_method = result.get(
            "verification_method"
        )
        user_data.verified_customer_id = result.get(
            "verified_customer_id"
        )
        user_data.verified_at = _parse_datetime(
            result.get("verified_at")
        )
        user_data.expires_at = _parse_datetime(
            result.get("expires_at")
        )
        user_data.identity_attempts = max(
            user_data.identity_attempts,
            int(result.get("attempt_count", 0)),
        )
        user_data.identity_verified = bool(result.get("verified"))
        return user_data.identity_verified

    try:
        verified = await asyncio.wait_for(
            IdentityVerificationTask(
                customer_id=customer.customer_id,
                verify_fn=verify,
                tts=active_persona_tts(context),
            ),
            timeout=GATE_TIMEOUT_S,
        )
    except Exception as exc:
        logger.warning(
            "identity gate fail-closed (%s: %s)",
            type(exc).__name__,
            exc or "no detail",
        )
        verified = False

    user_data.identity_verified = bool(verified) and identity_is_fresh(
        user_data
    )
    logger.info(
        "identity gate result: verified=%s customer_bound=%s",
        user_data.identity_verified,
        user_data.verified_customer_id == customer.customer_id,
    )
    return user_data.identity_verified
