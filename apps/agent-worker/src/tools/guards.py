"""Reusable sensitive-action preconditions (cookbook section 8).

ensure_identity_verified is the single gate every sensitive tool calls FIRST, so a tool
author cannot reach a domain action without a verified caller. It runs the
IdentityVerificationTask inline when needed and records the outcome in session user-data.
"""
from __future__ import annotations

import logging

from livekit.agents import RunContext

from clients.context_client import get_context_client
from tasks.identity_verification_task import IdentityVerificationTask

logger = logging.getLogger(__name__)


async def ensure_identity_verified(context: RunContext) -> bool:
    """Return True if the caller is (now) identity-verified; run step-up verification if not."""
    user_data = context.session.userdata

    if getattr(user_data, "identity_verified", False):
        return True

    if user_data.customer_context is None:
        logger.info("identity gate: caller is not resolved; cannot run step-up verification")
        return False

    verified = await IdentityVerificationTask(
        customer_id=user_data.customer_context.customer_id,
        verify_fn=get_context_client().verify_identity,
    )
    user_data.identity_verified = bool(verified)
    user_data.identity_attempts += 1
    logger.info("identity gate result: verified=%s", user_data.identity_verified)
    return user_data.identity_verified