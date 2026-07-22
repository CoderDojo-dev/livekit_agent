"""Network incident projection behind the NMS simulator.

Not a mock: projects the real oss.outages table (the schema comment already names it as the model
consumed by the NmsAdapter). An operator/supervisor populates outages; the voice agent reads them
in real time to tell a caller "yes, there's a known incident in your area, ETA ...". A resolved or
expired outage is not reported, so the agent never claims an incident that is over.

Matching is area-first then region, case-insensitive substring, because a caller says "Ariana" or
"downtown Tunis" while the record may hold "Ariana Ville" or region "Tunis".
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.oss import Outage

logger = logging.getLogger(__name__)


def _aware(value: datetime | None) -> datetime | None:
    """Normalize to UTC-aware. Some drivers/backends return naive datetimes; comparing a naive
    and an aware datetime raises, which would break the incident check at runtime."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _active(outage: Outage, now: datetime) -> bool:
    if outage.resolved:
        return False
    end_time = _aware(outage.end_time)
    if end_time is not None and end_time < now:
        return False
    return True


def get_network_status(session: Session, area: str) -> dict:
    """Return known active incidents affecting ``area`` (or its region) with an ETA.

    The shape matches what LiveNmsAdapter.get_network_status returns to the agent: a status plus a
    list of outages. An empty list means 'operational' - honestly, because it reflects the real
    table, not a hardcoded optimistic default.
    """
    needle = (area or "").strip().lower()
    if not needle:
        return {"area": area, "status": "unknown", "outages": [],
                "message": "no area provided"}

    now = datetime.now(UTC)
    candidates = session.scalars(
        select(Outage).where(Outage.resolved.is_(False)).order_by(Outage.start_time.desc())
    )
    matched = []
    for outage in candidates:
        if not _active(outage, now):
            continue
        hay = f"{outage.area or ''} {outage.region or ''}".lower()
        if needle in hay or (outage.area or "").lower() in needle or (outage.region or "").lower() in needle:
            matched.append(outage)

    outages = [
        {
            "area": o.area,
            "region": o.region,
            "affected_services": (o.affected_services or "").split(",") if o.affected_services else [],
            "severity": o.severity,
            "start_time": _aware(o.start_time).isoformat() if o.start_time else None,
            "eta": _aware(o.end_time).isoformat() if o.end_time else None,
        }
        for o in matched
    ]
    return {
        "area": area,
        "status": "incident" if outages else "operational",
        "outages": outages,
    }
