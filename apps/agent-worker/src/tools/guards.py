"""Reusable sensitive-action preconditions (cookbook section 8). Bounded + fail-closed."""
from __future__ import annotations

import asyncio
import logging

from clients.context_client import get_context_client
from livekit.agents import RunContext
from tasks.identity_verification_task import IdentityVerificationTask

logger = logging.getLogger(__name__)

GATE_TIMEOUT_S = 40.0  # > task deadline; only fires if the task machinery itself wedges


async def ensure_identity_verified(context: RunContext) -> bool:
    """Return True if the caller is (now) identity-verified; run step-up verification if not."""
    user_data = context.session.userdata

    if getattr(user_data, "identity_verified", False):
        return True

    if user_data.customer_context is None:
        logger.info("identity gate: caller not resolved; cannot run step-up verification")
        return False

    try:
        verified = await asyncio.wait_for(
            IdentityVerificationTask(
                customer_id=user_data.customer_context.customer_id,
                verify_fn=get_context_client().verify_identity,
            ),
            timeout=GATE_TIMEOUT_S,
        )
    except Exception as exc:  # includes asyncio.TimeoutError
        logger.warning("identity gate fail-closed (%s)", exc)
        verified = False

    user_data.identity_verified = bool(verified)
    try:
        user_data.identity_attempts += 1
    except Exception:
        pass
    logger.info("identity gate result: verified=%s", user_data.identity_verified)
    return user_data.identity_verified
