"""Persisted, customer-bound CIN-last-four verification."""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.auth import (
    CustomerCredential,
    VerificationEvent,
    VerificationSession,
)

VERIFICATION_TTL_MINUTES = 10
MAX_ATTEMPTS = 3


def _digest(customer_id: str, answer: str) -> str:
    key = os.getenv("AUTH_CIN_HMAC_KEY", "")
    if len(key) < 32:
        raise RuntimeError("AUTH_CIN_HMAC_KEY is missing or too short")

    normalized = "".join(char for char in answer if char.isdigit())
    message = f"cin_last4:{customer_id}:{normalized}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()


def _event(
    session: Session,
    verification_id: uuid.UUID,
    event_type: str,
    *,
    success: bool = False,
    reason: str | None = None,
) -> None:
    session.add(
        VerificationEvent(
            verification_session_id=verification_id,
            event_type=event_type,
            success=success,
            reason=reason,
        )
    )


def verify_cin_last4(
    session: Session,
    *,
    customer_id: str,
    call_session_id: str,
    answer: str,
) -> dict:
    """Verify CIN-last-four and persist every attempt without storing the answer."""
    now = datetime.now(UTC)
    customer_uuid = uuid.UUID(customer_id)
    call_uuid = uuid.UUID(call_session_id)

    credential = session.scalar(
        select(CustomerCredential).where(
            CustomerCredential.customer_id == customer_uuid,
            CustomerCredential.verifier_type == "cin_last4",
            CustomerCredential.active.is_(True),
        )
    )
    if credential is None:
        return {
            "verified": False,
            "status": "failed",
            "reason": "credential_not_configured",
        }

    verification = session.scalar(
        select(VerificationSession)
        .where(
            VerificationSession.customer_id == customer_uuid,
            VerificationSession.call_session_id == call_uuid,
        )
        .order_by(VerificationSession.created_at.desc())
    )

    if verification is not None and verification.status == "verified":
        if verification.expires_at > now:
            return {
                "verified": True,
                "status": "verified",
                "verification_session_id": str(verification.id),
                "verified_customer_id": customer_id,
                "verification_level": "cin_last4",
                "verification_method": "cin_last4",
                "verified_at": verification.verified_at,
                "expires_at": verification.expires_at,
                "attempt_count": verification.attempt_count,
            }

        verification.status = "expired"
        _event(
            session,
            verification.id,
            "expired",
            reason="verification_expired",
        )
        verification = None

    if verification is not None and verification.status == "locked":
        return {
            "verified": False,
            "status": "locked",
            "reason": "maximum_attempts_reached",
            "verification_session_id": str(verification.id),
            "attempt_count": verification.attempt_count,
        }

    if verification is None or verification.status in {"failed", "expired"}:
        verification = VerificationSession(
            customer_id=customer_uuid,
            call_session_id=call_uuid,
            method="cin_last4",
            status="pending",
            attempt_count=0,
            max_attempts=MAX_ATTEMPTS,
            expires_at=now + timedelta(minutes=VERIFICATION_TTL_MINUTES),
        )
        session.add(verification)
        session.flush()
        _event(session, verification.id, "started")

    verification.attempt_count += 1
    candidate_digest = _digest(customer_id, answer)
    verified = hmac.compare_digest(
        candidate_digest,
        credential.verifier_digest,
    )

    if verified:
        verification.status = "verified"
        verification.verified_at = now
        verification.expires_at = now + timedelta(
            minutes=VERIFICATION_TTL_MINUTES
        )
        _event(
            session,
            verification.id,
            "attempt_succeeded",
            success=True,
        )
    elif verification.attempt_count >= verification.max_attempts:
        verification.status = "locked"
        verification.locked_at = now
        _event(
            session,
            verification.id,
            "locked",
            reason="maximum_attempts_reached",
        )
    else:
        verification.status = "pending"
        _event(
            session,
            verification.id,
            "attempt_failed",
            reason="cin_mismatch",
        )

    session.commit()

    return {
        "verified": verified,
        "status": verification.status,
        "reason": None if verified else "cin_mismatch",
        "verification_session_id": str(verification.id),
        "verified_customer_id": customer_id if verified else None,
        "verification_level": "cin_last4" if verified else None,
        "verification_method": "cin_last4",
        "verified_at": verification.verified_at,
        "expires_at": verification.expires_at,
        "attempt_count": verification.attempt_count,
    }
