"""CRM schema (spec section 4): customer identity system of record + consent/interactions.

`crm.customers` is the single source of truth for identity; `national_id` carries the CIN
(closing review note 4). `crm.subscriptions` owns the MSISDN as a UNIQUE attribute - never a
join key (spec section 1).
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from persistence.base import Base, SoftDelete, Timestamps, UUIDPrimaryKey

_LANG = "preferred_language IN ('fr','ar','en')"


class Customer(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(_LANG, name="lang"),
        CheckConstraint("status IN ('active','suspended','closed')", name="status"),
        {"schema": "crm"},
    )

    national_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    contact_number: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'fr'"))
    segment: Mapped[str | None] = mapped_column(String(80), index=True)
    vip_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fraud_suspected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"), index=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")


class Subscription(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("plan_type IN ('PREPAID','POSTPAID')", name="plan_type"),
        CheckConstraint("status IN ('ACTIVE','SUSPENDED','BLOCKED','TERMINATED')", name="status"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    msisdn: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # UNIQUE attribute, never an FK
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    plan_code: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ACTIVE'"))
    roaming_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    activation_date: Mapped[datetime.date | None] = mapped_column(Date)

    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")


class ConsentRecord(UUIDPrimaryKey, Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(
            "consent_type IN ('call_recording','data_processing','marketing')", name="consent_type"
        ),
        CheckConstraint("language IN ('fr','ar','en')", name="language"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'call_recording'"))
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    captured_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CustomerInteraction(UUIDPrimaryKey, Base):
    __tablename__ = "customer_interactions"
    __table_args__ = (
        CheckConstraint("channel IN ('voice','chat','sms','email','whatsapp')", name="channel"),
        CheckConstraint("language IN ('fr','ar','en')", name="language"),
        {"schema": "crm"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'voice'"))
    detected_intent: Mapped[str | None] = mapped_column(String(80))
    resolution: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )