"""SIM lifecycle schema (spec section 7). Agent writes the identity-gated block/unblock case;
PUK/PIN secrets are never stored here (see spec section 7 supporting tables)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class BlockUnblockCase(UUIDPrimaryKey, Timestamps, Base):
    """An identity-gated SIM block/unblock/reactivate case (CDC 5.5). Idempotent + verdict-linked."""

    __tablename__ = "block_unblock_cases"
    __table_args__ = (
        CheckConstraint("action IN ('BLOCK','UNBLOCK','UNLOCK_PUK','REACTIVATE')", name="action"),
        CheckConstraint(
            "status IN ('pending','identity_verified','completed','escalated','rejected')", name="status"
        ),
        {"schema": "sim"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # loose ref (spec)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
