"""Audit schema (spec section 12.3-12.4): hash-chained tamper-evident ledger + PII token map."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CHAR, BigInteger, CheckConstraint, DateTime, Identity, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class AuditLedgerEntry(UUIDPrimaryKey, Base):
    __tablename__ = "audit_ledger"
    __table_args__ = ({"schema": "audit"},)

    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)  # strict chain ordering
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_reference: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PiiTokenMap(UUIDPrimaryKey, Base):
    __tablename__ = "pii_token_map"
    __table_args__ = (
        CheckConstraint(
            "pii_type IN ('msisdn','national_id','email','name','iccid')", name="pii_type"
        ),
        {"schema": "audit"},
    )

    token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    pii_type: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )