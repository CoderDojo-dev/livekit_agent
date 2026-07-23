"""Routing schema: the human advisors an escalation can reach (Blueprint, Escalation context).

The registry is the single source of truth for "who can take a call right now". Availability is a
real query - skill match, active, and under capacity - and a claim is atomic, so two simultaneous
escalations can never be handed the same advisor.

There is deliberately no heartbeat/auto-offline: the advisor's phone ringing is itself the
availability check. A stale 'available' flag costs one unanswered ring, after which the transfer
fails and the caller is offered a callback - which is honest, and cheaper than a background
liveness protocol.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Integer, String, text
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