"""Conversation & agent-runtime schema (spec section 11): the durable record of every call.

Written by the agent-worker through a NON-BLOCKING async writer (never on the voice path).
Turns / sentiment_samples are append-only; the supervisor-dashboard (P4) reads these.
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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey

_LANG = "detected_language IN ('fr','ar','en')"


class CallSession(UUIDPrimaryKey, Base):
    __tablename__ = "call_sessions"
    __table_args__ = (
        CheckConstraint("channel IN ('voice','chat')", name="channel"),
        CheckConstraint(
            "final_disposition IN ('resolved','escalated','dropped','abandoned')", name="disposition"
        ),
        {"schema": "conversation"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    msisdn: Mapped[str | None] = mapped_column(String(20))  # raw caller id, pre-resolution only
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'voice'"))
    livekit_room: Mapped[str | None] = mapped_column(String(120))
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    final_disposition: Mapped[str | None] = mapped_column(String(20))
    max_frustration_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0"))
    recording_consent: Mapped[bool | None] = mapped_column(Boolean)
    audio_record_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AgentUsageEvent(UUIDPrimaryKey, Base):
    """One provider-reported LLM usage metric, attributed at capture time."""

    __tablename__ = "agent_usage_events"
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation.call_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(160))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Turn(UUIDPrimaryKey, Base):
    __tablename__ = "turns"
    __table_args__ = (
        CheckConstraint("speaker IN ('caller','agent')", name="speaker"),
        CheckConstraint(_LANG, name="language"),
        UniqueConstraint("session_id", "turn_index", "speaker", name="session_turn_speaker"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(10), nullable=False)
    active_agent: Mapped[str | None] = mapped_column(String(40))
    detected_language: Mapped[str | None] = mapped_column(String(10))
    transcript_masked: Mapped[str | None] = mapped_column(Text)  # PII-masked (pii-shield)
    detected_intent: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class SentimentSample(UUIDPrimaryKey, Base):
    __tablename__ = "sentiment_samples"
    __table_args__ = (
        CheckConstraint("label IN ('positive','neutral','negative','angry')", name="label"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    label: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EscalationCase(UUIDPrimaryKey, Base):
    __tablename__ = "escalation_cases"
    __table_args__ = (
        CheckConstraint("target IN ('manager_agent','human_advisor')", name="target"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('transferred','queued','callback_scheduled','resolved')",
            name="resolution",
        ),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)  # spec Appendix A
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    dossier: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CallbackSchedule(UUIDPrimaryKey, Base):
    __tablename__ = "callback_schedules"
    __table_args__ = (
        CheckConstraint("status IN ('pending','completed','cancelled')", name="status"),
        {"schema": "conversation"},
    )

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.call_sessions.id")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    scheduled_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority_level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    # Lifecycle: who took it, what the caller actually asked for, and how it ended. Without these
    # a scheduled callback is a promise nobody can prove was kept.
    assigned_advisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routing.advisors.id", ondelete="SET NULL")
    )
    preferred_window: Mapped[str | None] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(String(60))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    outcome_note: Mapped[str | None] = mapped_column(String(500))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )