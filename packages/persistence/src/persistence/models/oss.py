"""OSS schema (spec section 8 / report #1): network inventory, alarms, outages.

Read models consumed by the NmsAdapter (`get_network_status`) and the technical persona when a
caller reports a fault - "is there a known outage in your area?".
"""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from persistence.base import Base, Timestamps, UUIDPrimaryKey


class NetworkElement(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "network_elements"
    __table_args__ = (
        CheckConstraint(
            "element_type IN ('cell_site','bts','router','switch','olt','core')", name="element_type"
        ),
        CheckConstraint("status IN ('active','degraded','down','maintenance')", name="status"),
        {"schema": "oss"},
    )

    element_type: Mapped[str] = mapped_column(String(40), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))


class Alarm(UUIDPrimaryKey, Base):
    __tablename__ = "alarms"
    __table_args__ = (
        CheckConstraint("severity IN ('critical','major','minor','warning')", name="severity"),
        {"schema": "oss"},
    )

    network_element_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("oss.network_elements.id"), index=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    alarm_type: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Outage(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "outages"
    __table_args__ = (
        CheckConstraint("severity IN ('critical','major','minor')", name="severity"),
        CheckConstraint(
            "cause IS NULL OR cause IN ('fiber_cut','power_failure','equipment_failure',"
            "'planned_maintenance','congestion','weather','third_party_damage')",
            name="cause",
        ),
        {"schema": "oss"},
    )

    region: Mapped[str | None] = mapped_column(String(80), index=True)
    area: Mapped[str | None] = mapped_column(String(120))
    affected_services: Mapped[str | None] = mapped_column(String(120))  # e.g. "mobile,data"
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'minor'"))
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    end_time: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # --- Patch v59 -------------------------------------------------------
    # Rattachement canonique (problème #3). Nullable pour ne pas casser les
    # lignes existantes ; la migration 0015 backfill par résolution du texte libre.
    area_code: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("reference.geo_areas.area_code"), index=True
    )
    # Ce qui se passe réellement, pour que l'agent puisse l'expliquer (problème #2).
    cause: Mapped[str | None] = mapped_column(String(60))
    description_fr: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)