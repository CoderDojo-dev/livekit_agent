"""Portal login identities: one shared account table for both front ends (P0-1).

Deliberately separate from models/auth.py: that module holds CALL-BOUND step-up verification
state (auth.verification_sessions.call_session_id is NOT NULL). These two tables hold WEB login
state. Same `auth` schema, different lifecycle.

A client row is a login ATTACHED to an existing crm.customers row - the portal never creates
telecom data. A staff row has no customer and carries one of the three backend roles.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey

STAFF_ROLES = ("conseiller", "superviseur", "administrateur")
CLIENT_ROLE = "client"

_KIND_ROLE_CUSTOMER = (
    "(kind = 'staff' AND customer_id IS NULL "
    "AND role IN ('conseiller','superviseur','administrateur')) "
    "OR (kind = 'client' AND customer_id IS NOT NULL AND role = 'client')"
)


class PortalAccount(UUIDPrimaryKey, Timestamps, Base):
    """A web login. At most one per staff member, at most one per customer."""

    __tablename__ = "portal_accounts"
    __table_args__ = (
        CheckConstraint("kind IN ('staff','client')", name="kind"),
        CheckConstraint(
            "role IN ('conseiller','superviseur','administrateur','client')",
            name="role",
        ),
        CheckConstraint(_KIND_ROLE_CUSTOMER, name="kind_role_customer"),
        CheckConstraint("failed_attempts >= 0", name="failed_attempts"),
        UniqueConstraint("email", name="uq_portal_accounts_email"),
        # Postgres permits many NULLs in a UNIQUE index, so every staff row coexists
        # while a customer can hold at most one client login.
        UniqueConstraint("customer_id", name="uq_portal_accounts_customer_id"),
        {"schema": "auth"},
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'scrypt'")
    )
    password_params: Mapped[str] = mapped_column(String(60), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm.customers.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class PortalSession(UUIDPrimaryKey, Timestamps, Base):
    """A live browser session.

    The token itself is never stored, only its SHA-256 digest: a leaked database cannot be
    replayed against the API. Server-side rows are what make logout, expiry and
    "sign out of all devices" real rather than cosmetic.
    """

    __tablename__ = "portal_sessions"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_portal_sessions_token_digest"),
        {"schema": "auth"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.portal_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(200))