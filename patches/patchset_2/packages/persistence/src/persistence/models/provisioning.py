"""Provisioning schema (spec section 8 / report #2): activation requests, SIM orders, plan changes.

Written by the execution-service when an AccountServicesAgent action (CHANGE_PLAN / ACTIVATE_ROAMING)
succeeds - so this schema is exercised, not dead. Carries idempotency_key + policy_verdict_id like
every other write projection.
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class ProvisioningRequest(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "provisioning_requests"
    __table_args__ = (
        CheckConstraint("status IN ('pending','in_progress','completed','failed')", name="status"),
        {"schema": "provisioning"},
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("crm.customers.id"))
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    policy_verdict_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class SimOrder(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "sim_orders"
    __table_args__ = (
        CheckConstraint("sim_type IN ('physical','esim')", name="sim_type"),
        CheckConstraint("status IN ('requested','shipped','activated','cancelled')", name="status"),
        {"schema": "provisioning"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id")
    )
    sim_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'physical'"))
    iccid: Mapped[str | None] = mapped_column(String(22))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'requested'"))
    tracking_code: Mapped[str | None] = mapped_column(String(60))


class PlanChangeHistory(UUIDPrimaryKey, Base):
    __tablename__ = "plan_change_history"
    __table_args__ = (
        CheckConstraint("changed_by IN ('agent','self_service','advisor')", name="changed_by"),
        {"schema": "provisioning"},
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.subscriptions.id"), index=True
    )
    from_plan: Mapped[str | None] = mapped_column(String(60))
    to_plan: Mapped[str] = mapped_column(String(60), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'agent'"))
    effective_date: Mapped[datetime.date | None] = mapped_column(Date)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )