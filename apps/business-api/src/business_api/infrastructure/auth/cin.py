"""Read-only mirror of the CIN-last-four verifier used by the voice channel.

The canonical implementation is context_service.auth_service._digest(). business-api cannot
import it (services/ are not installed in this image), and calling POST /verify-identity would be
wrong for the web: that endpoint opens an auth.verification_sessions row bound to a
call_session_id, and a signup has no call to bind to.

So the construction is mirrored here byte for byte and PINNED by
tests/test_auth_cin.py::test_digest_matches_pinned_vector. If either side ever drifts, that test
fails.

This module never writes. Signup throttling lives in rate_limit.py, deliberately NOT in
auth.verification_sessions - web attempts must not pollute call-bound verification history.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.auth import CustomerCredential


def digest(customer_id: str, answer: str) -> str:
    """HMAC-SHA-256 of the normalised CIN last four, salted with the customer id.

    Mirrors context_service.auth_service._digest exactly: same normalisation (digits only),
    same message layout, same key, same hash.
    """
    key = os.getenv("AUTH_CIN_HMAC_KEY", "")
    if len(key) < 32:
        raise RuntimeError("AUTH_CIN_HMAC_KEY is missing or too short")

    normalized = "".join(char for char in answer if char.isdigit())
    message = f"cin_last4:{customer_id}:{normalized}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def matches(session: Session, customer_id: uuid.UUID, answer: str) -> bool:
    """True when ``answer`` matches the active cin_last4 verifier for ``customer_id``."""
    credential = session.scalar(
        select(CustomerCredential).where(
            CustomerCredential.customer_id == customer_id,
            CustomerCredential.verifier_type == "cin_last4",
            CustomerCredential.active.is_(True),
        )
    )
    if credential is None:
        return False
    return hmac.compare_digest(
        digest(str(customer_id), answer), credential.verifier_digest
    )