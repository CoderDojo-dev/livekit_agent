"""OCS prepaid schema (spec section 6): live balances (moved off the subscription row).

A read-through view (crm.v_subscription_live) re-presents the live balance to the Context
façade without duplicating mutable state. Usage/recharge write paths land with execution.
"""
from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from persistence.models.crm import Customer, Subscription

from persistence.base import Base, UUIDPrimaryKey


class BalanceAccount(UUIDPrimaryKey, Base):
    __tablename__ = "balance_accounts"
    __table_args__ = (
        CheckConstraint("balance_type IN ('main','data','voice','sms')", name="balance_type"),
        CheckConstraint("balance_unit IN ('TND','GB','MB','MIN','SMS')", name="balance_unit"),
        CheckConstraint("status IN ('active','expired','suspended')", name="status"),
        UniqueConstraint("subscription_id", "balance_type", name="subscription_type"),
        {"schema": "ocs"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False)
    balance_type: Mapped[str] = mapped_column(String(20), nullable=False)
    balance_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, server_default=text("0"))
    balance_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    expiry_date: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    subscription: Mapped[Subscription] = relationship("Subscription")
    customer: Mapped[Customer] = relationship("Customer")


class Recharge(UUIDPrimaryKey, Base):
    """A prepaid top-up (spec section 6.2). `idempotency_key` mirrors execution.action_ledger."""

    __tablename__ = "recharges"
    __table_args__ = (
        CheckConstraint("channel IN ('app','web','ussd','scratch_card','agent')", name="channel"),
        CheckConstraint("status IN ('pending','completed','failed')", name="status"),
        {"schema": "ocs"},
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    recharge_code: Mapped[str | None] = mapped_column(String(50))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    bonus_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    transaction_reference: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
