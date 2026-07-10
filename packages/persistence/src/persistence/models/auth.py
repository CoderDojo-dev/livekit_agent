"""Persisted, customer-bound step-up authentication state."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class CustomerCredential(UUIDPrimaryKey, Timestamps, Base):
    """Protected verifier used for customer step-up authentication."""

    __tablename__ = "customer_credentials"
    __table_args__ = (
        CheckConstraint(
            "verifier_type IN ('cin_last4')",
            name="verifier_type",
        ),
        UniqueConstraint(
            "customer_id",
            "verifier_type",
            name="uq_customer_credentials_customer_type",
        ),
        {"schema": "auth"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm.customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verifier_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'cin_last4'"),
    )
    verifier_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    key_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class VerificationSession(UUIDPrimaryKey, Timestamps, Base):
    """A bounded authentication attempt tied to one customer and call."""

    __tablename__ = "verification_sessions"
    __table_args__ = (
        CheckConstraint(
            "method IN ('cin_last4')",
            name="method",
        ),
        CheckConstraint(
            "status IN "
            "('pending','verified','failed','locked','expired')",
            name="status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="attempt_bounds",
        ),
        Index(
            "ix_verification_sessions_customer_status",
            "customer_id",
            "status",
        ),
        {"schema": "auth"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crm.customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'cin_last4'"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("3"),
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    verified_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    locked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
    )


class VerificationEvent(UUIDPrimaryKey, Base):
    """Append-only authentication event. Submitted CIN data is never stored."""

    __tablename__ = "verification_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('started','attempt_succeeded','attempt_failed',"
            "'locked','expired')",
            name="event_type",
        ),
        {"schema": "auth"},
    )

    verification_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "auth.verification_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    reason: Mapped[str | None] = mapped_column(String(120))
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
