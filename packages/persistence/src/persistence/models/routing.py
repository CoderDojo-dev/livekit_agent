"""Routing schema: the human advisors an escalation can reach (Blueprint, Escalation context).

The registry is the single source of truth for "who can take a call right now". Availability is a
real query - skill match, active, and under capacity - and a claim is atomic, so two simultaneous
escalations can never be handed the same advisor.

There is deliberately no heartbeat/auto-offline: the advisor's phone ringing is itself the
availability check. A stale 'available' flag costs one unanswered ring, after which the transfer
fails and the caller is offered a callback - which is honest, and cheaper than a background
liveness protocol.

Also hosts AdvisorShift (the recurring weekly working grid) and AdvisorTimeOff (dated exceptions)
which together turn the static "is_on_call" flag into an honest answer to "can anyone work at this
exact moment?"
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class Advisor(UUIDPrimaryKey, Timestamps, Base):
    """A human advisor reachable by phone or SIP for escalated calls."""

    __tablename__ = "advisors"
    __table_args__ = (
        CheckConstraint("status IN ('available','busy','offline')", name="status"),
        CheckConstraint("max_concurrent_calls > 0", name="positive_capacity"),
        CheckConstraint("active_calls >= 0", name="non_negative_active"),
        {"schema": "routing"},
    )

    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    sip_uri: Mapped[str | None] = mapped_column(String(255))
    skills: Mapped[str] = mapped_column(String(200), nullable=False, server_default=text("'general'"))
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'fr'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'offline'"))
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    active_calls: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_on_call: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class AdvisorShift(UUIDPrimaryKey, Timestamps, Base):
    """One recurring weekly working window for one advisor, in local business time.

    Storing the RULE instead of materialising every future slot is deliberate: a schedule change
    takes one UPDATE and applies immediately to every future projection, and the table stays a
    few dozen rows instead of growing forever. Minutes-since-midnight is used rather than TIME so
    that arithmetic (does this slot fall inside the window?) is a plain integer comparison, in SQL
    as well as in Python.
    """

    __tablename__ = "advisor_shifts"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("start_minute >= 0 AND start_minute < 1440", name="start_range"),
        CheckConstraint("end_minute > start_minute AND end_minute <= 1440", name="end_after_start"),
        UniqueConstraint("advisor_id", "weekday", "start_minute", name="uq_shift_slot"),
        Index("ix_shift_lookup", "weekday", "is_active"),
        {"schema": "routing"},
    )

    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routing.advisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 0 = Monday ... 6 = Sunday, matching datetime.weekday() so no translation layer is needed.
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class AdvisorTimeOff(UUIDPrimaryKey, Timestamps, Base):
    """A dated exception that removes an advisor from the schedule (leave, training, sick day).

    Exceptions are a separate table rather than holes punched in the weekly grid: the grid stays
    the contract of employment, the exception stays auditable and reversible, and deleting the
    exception restores the schedule exactly.
    """

    __tablename__ = "advisor_time_off"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="time_off_ordered"),
        Index("ix_time_off_window", "starts_at", "ends_at"),
        {"schema": "routing"},
    )

    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routing.advisors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))