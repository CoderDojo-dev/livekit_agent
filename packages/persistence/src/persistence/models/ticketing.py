"""Ticketing schema (spec section 10): a thin local mirror of GLPI (GLPI stays source of truth)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
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
    last_synced_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
