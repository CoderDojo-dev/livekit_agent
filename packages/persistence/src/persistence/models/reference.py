"""Reference catalogs (spec section 13): admin-managed, read-mostly shared data.

`business_rules` is the versioned, governable registry of the Policy rules (spec section 13.1):
the deterministic engine still executes in code, while this table is the published, audited catalog
that the business-api exposes for review/versioning. error_catalog/products/recharge_catalog back
agent-facing messages and plan/recharge information.
"""
from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
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


class GeoArea(UUIDPrimaryKey, Timestamps, Base):
    """Référentiel canonique des zones tunisiennes (gouvernorat / délégation / localité).

    Source de vérité unique pour « ce lieu existe-t-il, et à quelle zone correspond-il ? ».
    oss.outages.area_code pointe ici : une panne ne PEUT donc plus nommer une zone
    inexistante. Le problème #3 devient structurellement impossible grâce à la clé
    étrangère, sans code de validation dispersé dans les services.
    """

    __tablename__ = "geo_areas"
    __table_args__ = (
        CheckConstraint(
            "area_type IN ('governorate','delegation','locality')", name="area_type"
        ),
        {"schema": "reference"},
    )

    area_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name_fr: Mapped[str] = mapped_column(String(120), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    area_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("reference.geo_areas.area_code"), index=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class GeoAlias(UUIDPrimaryKey, Base):
    """Toute forme parlée ou écrite qui résout vers une zone canonique.

    ``normalized`` est la clé de recherche déterministe (sans accents, sans diacritiques
    arabes, sans article, minuscule) CALCULÉE À L'ÉCRITURE et stockée. La résolution est
    donc une seule égalité indexée en base, jamais un parcours-et-compare en mémoire.
    """

    __tablename__ = "geo_aliases"
    __table_args__ = (
        UniqueConstraint("normalized", name="uq_geo_alias_normalized"),
        {"schema": "reference"},
    )

    area_code: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("reference.geo_areas.area_code"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
