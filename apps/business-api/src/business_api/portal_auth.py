"""Portal authentication use cases (P0-1).

Owns the rules: lockout, session lifetime, password change, and the subscriber claim that binds a
new client login to an existing crm.customers row. main.py only validates input and maps outcomes
onto HTTP status codes.
"""
from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from business_api.infrastructure.auth import cin, passwords, tokens
from persistence.models.crm import Customer, Subscription
from persistence.models.portal_identity import PortalAccount, PortalSession

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 10

# A real hash of a throwaway secret. Verifying against it when the email is unknown burns the
# same scrypt work as a real check, so response time does not disclose whether an account exists.
_DECOY_HASH = passwords.hash_password(secrets.token_urlsafe(16))[2]


class AuthError(Exception):
    """Authentication failure. ``code`` selects the HTTP mapping in main.py."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def session_ttl_seconds() -> int:
    """Backend session lifetime. Defaults to 8 h, matching ADMIN_SESSION_TTL."""
    try:
        return max(300, int(os.getenv("PORTAL_SESSION_TTL", "28800")))
    except ValueError:
        return 28800


# ---------------------------------------------------------------- sign in

def authenticate(session: Session, email: str, password: str) -> PortalAccount:
    """Return the account for valid credentials, else raise AuthError.

    A wrong address and a wrong password are indistinguishable: both spend one scrypt
    computation and both raise ``invalid_credentials``.
    """
    normalized = email.strip().lower()
    now = datetime.now(UTC)

    account = session.scalar(
        select(PortalAccount).where(PortalAccount.email == normalized)
    )

    if account is None:
        passwords.verify_password(
            password, passwords.ALGORITHM, passwords.default_params(), _DECOY_HASH
        )
        raise AuthError("invalid_credentials", "Incorrect email or password")

    if not account.is_active:
        raise AuthError("invalid_credentials", "Incorrect email or password")

    correct = passwords.verify_password(
        password, account.password_algo, account.password_params, account.password_hash
    )

    if account.locked_until is not None and account.locked_until > now:
        # Only someone who already knows the password learns that a lock exists; a guesser
        # keeps seeing the generic answer and learns nothing.
        if correct:
            raise AuthError(
                "locked", "Too many failed attempts. Try again in a few minutes."
            )
        raise AuthError("invalid_credentials", "Incorrect email or password")

    if not correct:
        account.failed_attempts += 1
        if account.failed_attempts >= MAX_FAILED_ATTEMPTS:
            account.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            account.failed_attempts = 0
        session.commit()
        raise AuthError("invalid_credentials", "Incorrect email or password")

    account.failed_attempts = 0
    account.locked_until = None
    account.last_login_at = now
    session.commit()
    return account


def open_session(
    session: Session,
    account: PortalAccount,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, datetime]:
    """Create a session row and return ``(token, expires_at)``. The token is never stored."""
    token = tokens.new_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=session_ttl_seconds())
    session.add(
        PortalSession(
            account_id=account.id,
            token_digest=tokens.token_digest(token),
            expires_at=expires_at,
            ip_address=ip_address[:45] if ip_address else None,
            user_agent=user_agent[:200] if user_agent else None,
        )
    )
    session.commit()
    return token, expires_at


def revoke_session(session: Session, token: str) -> None:
    """Idempotent logout: revoking an unknown or already-revoked token is a no-op."""
    row = session.scalar(
        select(PortalSession).where(
            PortalSession.token_digest == tokens.token_digest(token)
        )
    )
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.commit()


def revoke_all(session: Session, account_id: uuid.UUID) -> int:
    """Sign out every device for an account. Returns how many sessions were closed."""
    now = datetime.now(UTC)
    rows = list(
        session.scalars(
            select(PortalSession).where(
                PortalSession.account_id == account_id,
                PortalSession.revoked_at.is_(None),
            )
        )
    )
    for row in rows:
        row.revoked_at = now
    if rows:
        session.commit()
    return len(rows)


# ---------------------------------------------------------------- password change

def change_password(
    session: Session, account_id: uuid.UUID, current: str, replacement: str
) -> int:
    """Rotate a password and close every other session. Returns sessions revoked.

    This is what makes ADMIN_PASSWORD a bootstrap value rather than a permanent one: the seed
    creates the row, the operator changes the password in the product, and the new hash lives in
    the database. The seed never overwrites it (see seed_admin.py).
    """
    account = session.get(PortalAccount, account_id)
    if account is None or not account.is_active:
        raise AuthError("invalid_credentials", "Incorrect password")

    if not passwords.verify_password(
        current, account.password_algo, account.password_params, account.password_hash
    ):
        raise AuthError("invalid_credentials", "Incorrect password")

    if len(replacement) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            "weak_password",
            f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters.",
        )
    if replacement == current:
        raise AuthError("weak_password", "Choose a password you have not used here before.")

    algorithm, params, encoded = passwords.hash_password(replacement)
    account.password_algo = algorithm
    account.password_params = params
    account.password_hash = encoded
    account.password_changed_at = datetime.now(UTC)
    session.commit()

    return revoke_all(session, account.id)


# ---------------------------------------------------------------- client signup

def signup_client(
    session: Session, *, msisdn: str, cin_last4: str, email: str, password: str
) -> PortalAccount:
    """Bind a new client login to the subscriber that already owns ``msisdn``.

    The portal never creates telecom data. The caller proves they are the subscriber using the
    SAME verifier the voice channel uses (auth.customer_credentials, cin_last4), and a login row
    is then attached to the customer that already exists. Balance, plan, invoices and tickets are
    never entered here - they are already in crm/billing/ocs keyed by customer_id, and surface
    through /api/v1/me/* using the customer_id carried by the token.

    Every failure below the password check raises the SAME error. Distinguishing "unknown number"
    from "wrong CIN" from "already registered" would turn this endpoint into a subscriber
    enumeration oracle.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(
            "weak_password",
            f"Choose a password of at least {MIN_PASSWORD_LENGTH} characters.",
        )

    generic = AuthError(
        "signup_failed", "We could not match those details to an account."
    )

    normalized_msisdn = "".join(
        char for char in msisdn.strip() if char.isdigit() or char == "+"
    )
    normalized_email = email.strip().lower()
    if not normalized_msisdn or "@" not in normalized_email:
        raise generic

    subscription = session.scalar(
        select(Subscription).where(Subscription.msisdn == normalized_msisdn)
    )
    if subscription is None:
        raise generic

    customer = session.get(Customer, subscription.customer_id)
    if customer is None or customer.deleted_at is not None or customer.status == "closed":
        raise generic

    # A suspended subscriber must still be able to sign in and pay, so subscription.status is
    # deliberately NOT filtered here. Only a closed/deleted customer is refused.
    if not cin.matches(session, customer.id, cin_last4):
        raise generic

    taken = session.scalar(
        select(PortalAccount).where(
            (PortalAccount.customer_id == customer.id)
            | (PortalAccount.email == normalized_email)
        )
    )
    if taken is not None:
        raise generic

    algorithm, params, encoded = passwords.hash_password(password)
    account = PortalAccount(
        kind="client",
        email=normalized_email,
        password_hash=encoded,
        password_algo=algorithm,
        password_params=params,
        role="client",
        customer_id=customer.id,
        is_active=True,
        password_changed_at=datetime.now(UTC),
    )
    session.add(account)
    session.commit()
    return account