"""Execution schema (spec section 12.2): idempotent action ledger, append-mostly.

`idempotency_key` is UNIQUE - the contract that an action runs at most once across retries.
Every row references the `policy_verdict_id` that authorized it (no action without a verdict).
"""
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class ActionLedger(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "action_ledger"
    __table_args__ = (
        CheckConstraint("status IN ('pending','succeeded','failed','retrying')", name="status"),
        {"schema": "execution"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    policy_verdict_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy.policy_verdicts.id"), nullable=False
    )
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    adapter_reference: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)