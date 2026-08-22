"""Ticketing schema (spec section 10): a thin local mirror of GLPI (GLPI stays source of truth)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, UUIDPrimaryKey


class Ticket(UUIDPrimaryKey, Base):
    """Local cache row pointing at the real GLPI ticket id (spec section 10)."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('network_complaint','formal_complaint','technical','billing','other')",
            name="category",
        ),
        CheckConstraint(
            "status IN ('open','in_progress','pending','resolved','closed')", name="status"
        ),
        CheckConstraint("priority IS NULL OR priority IN ('low','medium','high','urgent')", name="priority"),
        # A note and its timestamp travel together (migration 0020).
        CheckConstraint(
            "(admin_note IS NULL) = (note_updated_at IS NULL)", name="admin_note_timestamped"
        ),
        {"schema": "ticketing"},
    )

    glpi_ticket_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'other'"))
    subject: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"))
    priority: Mapped[str | None] = mapped_column(String(10))
    # --- Administrator note (migration 0020) -------------------------------------------------
    # Written when an admin changes a ticket's state from the console. It is mirrored here rather
    # than kept only in GLPI because the agent reads tickets through this table: GLPI's `solution`
    # field is never read back by LiveGlpiClient.get(), so a note stored only upstream would be
    # invisible on the next call. Nullable and additive - a ticket without a note behaves exactly
    # as it did before.
    admin_note: Mapped[str | None] = mapped_column(Text)
    note_author: Mapped[str | None] = mapped_column(String(255))
    note_updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    # When the TICKET last changed, as distinct from last_synced_at above, which is bumped by
    # every reconciliation pass including one that changed nothing. `onupdate` means every ORM
    # mutation already in the codebase - mirror_update, mirror_set_status, mirror_resolve,
    # upsert_from_glpi - stamps this without a call-site change (migration 0021).
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )
