"""Policy schema (spec section 12.1): every authorize/refuse/escalate decision, append-only."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class PolicyVerdict(UUIDPrimaryKey, Base):
    __tablename__ = "policy_verdicts"
    __table_args__ = (
        CheckConstraint("direction IN ('inbound','outbound')", name="direction"),
        CheckConstraint("verdict IN ('AUTHORIZED','REFUSED','ESCALATE')", name="verdict"),
        {"schema": "policy"},
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'inbound'"))
    verdict: Mapped[str] = mapped_column(String(12), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )