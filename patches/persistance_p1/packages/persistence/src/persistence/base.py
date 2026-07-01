"""Declarative base + shared column mixins (spec section 3 global conventions).

Every table inherits: UUID primary key (`uuid_generate_v4()`), UTC `created_at`/`updated_at`
(with the `set_updated_at` trigger attached in the migration), and - where master data -
a nullable `deleted_at` for soft delete. Money is NUMERIC, never float.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint/index names (stable migrations).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base carrying the project metadata/naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKey:
    """`id UUID PRIMARY KEY DEFAULT uuid_generate_v4()` (spec hard rule 1)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )


class Timestamps:
    """`created_at` / `updated_at` (UTC). The `updated_at` trigger is attached in the migration."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SoftDelete:
    """`deleted_at` for master/reference data (operational logs are append-only instead)."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)