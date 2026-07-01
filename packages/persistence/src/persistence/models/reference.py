"""Reference catalogs (spec section 13): admin-managed, read-mostly shared data.

`business_rules` is the versioned, governable registry of the Policy rules (spec section 13.1):
the deterministic engine still executes in code, while this table is the published, audited catalog
that the business-api exposes for review/versioning. error_catalog/products/recharge_catalog back
agent-facing messages and plan/recharge information.
"""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class BusinessRule(UUIDPrimaryKey, Timestamps, Base):
    """A versioned Policy rule definition (spec section 13.1), consumed/governed via business-api."""

    __tablename__ = "business_rules"
    __table_args__ = ({"schema": "reference"},)

    rule_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    domain: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    definition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ErrorCatalog(UUIDPrimaryKey, Base):
    """Canonical error codes surfaced to agents, localized (spec section 13.1)."""

    __tablename__ = "error_catalog"
    __table_args__ = ({"schema": "reference"},)

    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(String(40))
    message_fr: Mapped[str | None] = mapped_column(Text)
    message_ar: Mapped[str | None] = mapped_column(Text)
    message_en: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Product(UUIDPrimaryKey, Base):
    """Plan/product catalog (spec section 13.1)."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("plan_type IN ('PREPAID','POSTPAID')", name="plan_type"),
        {"schema": "reference"},
    )

    product_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RechargeCatalog(UUIDPrimaryKey, Base):
    """Prepaid recharge denominations (spec section 13.1)."""

    __tablename__ = "recharge_catalog"
    __table_args__ = ({"schema": "reference"},)

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    bonus_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
