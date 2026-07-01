"""Billing schema (spec section 5): postpaid accounts, invoices, line items.

Payments / payment_plans (write paths) land with the execution-service persistence slice.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from persistence.models.crm import Customer

from persistence.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey


class Account(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("account_type IN ('postpaid','hybrid')", name="account_type"),
        CheckConstraint("billing_cycle_day BETWEEN 1 AND 28", name="cycle_day"),
        CheckConstraint("status IN ('active','dunning','suspended','closed')", name="status"),
        {"schema": "billing"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'postpaid'"))
    billing_cycle_day: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("15"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    customer: Mapped["Customer"] = relationship("Customer")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="account")


class Invoice(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','issued','paid','partial','overdue','disputed','void')", name="status"
        ),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    issue_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    outstanding_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'issued'"), index=True)

    account: Mapped["Account"] = relationship(back_populates="invoices")
    customer: Mapped["Customer"] = relationship("Customer")
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(UUIDPrimaryKey, Base):
    __tablename__ = "invoice_items"
    __table_args__ = ({"schema": "billing"},)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default=text("1"))
    unit_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, server_default=text("0"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class Payment(UUIDPrimaryKey, Timestamps, Base):
    """A payment capture (spec section 5.1). `idempotency_key` mirrors execution.action_ledger."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("method IN ('card','bank_transfer','wallet','voucher','cash')", name="method"),
        CheckConstraint("status IN ('pending','succeeded','failed','refunded')", name="status"),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.invoices.id"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'TND'"))
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    gateway_reference: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentPlan(UUIDPrimaryKey, Timestamps, Base):
    """A payment deferral / installment plan (spec section 5.1, CDC 5.3)."""

    __tablename__ = "payment_plans"
    __table_args__ = (
        CheckConstraint("installment_count BETWEEN 1 AND 12", name="installments"),
        CheckConstraint(
            "status IN ('proposed','active','completed','defaulted','cancelled')", name="status"
        ),
        {"schema": "billing"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing.accounts.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    installment_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    deferral_until: Mapped[datetime.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # loose ref (spec)


class Notification(UUIDPrimaryKey, Base):
    """Outbound customer notification log (spec section 5.2): reminder/alert/confirmation dispatch."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('sms','whatsapp','email')", name="channel"),
        CheckConstraint("status IN ('queued','sent','failed')", name="status"),
        {"schema": "billing"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'sent'"))
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
