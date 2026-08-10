"""Who is calling. Established here, once, for every gated endpoint.

Two kinds of principal exist:

  * a human session - `Authorization: Bearer <token>` issued by POST /api/v1/auth/login and
    revalidated against auth.portal_sessions on every request, so logout, expiry and
    "sign out of all devices" take effect immediately rather than at the next token expiry;

  * the internal machine caller - `X-API-Key` matching INTERNAL_API_KEY, the key
    packages/service-auth already defines and that the worker already sends to context-service.
    It is pinned to the LOWEST staff rank, conseiller, because every business-api route the
    worker uses is a conseiller route: /advisors/claim, /advisors/{id}/release,
    /advisors/on-call, /callbacks/slots, /callbacks/check, /callbacks/reserve.

The X-Role header is not read anywhere in this file or anywhere else after this patch. A caller
may still send it; it has no effect.

Session reuse note: current_principal depends on the SAME `get_session` callable that DbSession
uses, so FastAPI's per-request dependency cache hands both the identical Session. One request
still opens exactly one database connection.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from business_api.infrastructure.auth.tokens import token_digest
from persistence import get_session
from persistence.models.portal_identity import PortalAccount, PortalSession

MACHINE_ROLE = "conseiller"
MACHINE_SUBJECT = "agent-worker"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. ``customer_id`` is set only for portal clients."""

    subject: str
    kind: str  # "staff" | "client" | "service"
    role: str  # conseiller | superviseur | administrateur | client
    account_id: UUID | None = None
    customer_id: UUID | None = None
    session_id: UUID | None = None


_MACHINE = Principal(subject=MACHINE_SUBJECT, kind="service", role=MACHINE_ROLE)


def _internal_key() -> str | None:
    return os.getenv("INTERNAL_API_KEY")


def bearer_token(authorization: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def resolve_session(session: Session, token: str) -> Principal | None:
    """Validate an opaque bearer token against auth.portal_sessions. None when unusable."""
    row = session.execute(
        select(PortalSession, PortalAccount)
        .join(PortalAccount, PortalAccount.id == PortalSession.account_id)
        .where(PortalSession.token_digest == token_digest(token))
    ).first()
    if row is None:
        return None

    portal_session, account = row
    if portal_session.revoked_at is not None:
        return None
    if portal_session.expires_at <= datetime.now(UTC):
        return None
    if not account.is_active:
        return None

    return Principal(
        subject=account.email,
        kind=account.kind,
        role=account.role,
        account_id=account.id,
        customer_id=account.customer_id,
        session_id=portal_session.id,
    )


def current_principal(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve the caller, or 401. Fail closed: no valid credential means no access."""
    expected = _internal_key()
    if x_api_key and expected and hmac.compare_digest(x_api_key, expected):
        return _MACHINE

    token = bearer_token(authorization)
    if token:
        principal = resolve_session(session, token)
        if principal is not None:
            return principal

    raise HTTPException(status_code=401, detail="not authenticated")


def current_client(
    principal: Annotated[Principal, Depends(current_principal)],
) -> Principal:
    """A portal client. Staff and machine principals are refused.

    /api/v1/me/* reads customer_id from HERE, never from the URL or the body, so there is no
    identifier for a caller to tamper with and IDOR is impossible by construction.
    """
    if principal.kind != "client" or principal.customer_id is None:
        raise HTTPException(status_code=403, detail="requires a client account")
    return principal