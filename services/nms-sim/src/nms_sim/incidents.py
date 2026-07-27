"""Network incident projection behind the NMS simulator.

Not a mock: projects the real oss.outages table (the schema comment already names it as the model
consumed by the NmsAdapter). An operator/supervisor populates outages; the voice agent reads them
in real time to tell a caller "yes, there's a known incident in your area, ETA ...". A resolved or
expired outage is not reported, so the agent never claims an incident that is over.

Patch v59: zone resolver + honest states (area_unknown / operational / incident / unavailable).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from nms_sim import geo_resolver
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


_ANCESTORS_SQL = text("""
    WITH RECURSIVE chain AS (
        SELECT area_code, parent_code FROM reference.geo_areas
        WHERE area_code = :code
        UNION ALL
        SELECT g.area_code, g.parent_code
        FROM reference.geo_areas g JOIN chain c ON g.area_code = c.parent_code
    )
    SELECT area_code FROM chain
""")

_DESCENDANTS_SQL = text("""
    WITH RECURSIVE tree AS (
        SELECT area_code FROM reference.geo_areas WHERE area_code = :code
        UNION ALL
        SELECT g.area_code
        FROM reference.geo_areas g JOIN tree t ON g.parent_code = t.area_code
    )
    SELECT area_code FROM tree
""")

_DESCRIPTIONS = {"fr": "description_fr", "ar": "description_ar", "en": "description_en"}


def _describe(outage: Outage, language: str) -> str | None:
    """Message client dans sa langue, avec repli FR. Jamais de texte inventé."""
    column = _DESCRIPTIONS.get(language, "description_fr")
    return getattr(outage, column, None) or outage.description_fr


def get_network_status(session: Session, area: str, language: str = "fr") -> dict:
    """Incidents actifs connus pour ``area``.

    Quatre états mutuellement exclusifs, jamais confondus (problème #4) :
      - "area_unknown" : zone non résolue -> RIEN n'a pu être vérifié ;
      - "incident"     : zone résolue, incident(s) actif(s) ;
      - "operational"  : zone résolue, aucun incident actif - affirmation prouvée ;
      - "unavailable"  : produit par le client en cas de panne de transport.
    """
    if not (area or "").strip():
        return {
            "area": area,
            "status": "area_unknown",
            "verified": False,
            "reason": "no_area_provided",
            "outages": [],
            "suggestions": [],
        }

    resolved = geo_resolver.resolve(session, area)
    if resolved is None:
        return {
            "area": area,
            "status": "area_unknown",
            "verified": False,
            "reason": "area_not_in_referential",
            "outages": [],
            "suggestions": geo_resolver.suggest(session, area),
        }

    # Ascendants : une panne déclarée sur le gouvernorat concerne la délégation
    # du client. Descendants : une panne déclarée sur une délégation interdit
    # d'affirmer que tout va bien sur le gouvernorat entier.
    ancestors = {
        r.area_code
        for r in session.execute(_ANCESTORS_SQL, {"code": resolved.area_code}).all()
    }
    descendants = {
        r.area_code
        for r in session.execute(
            _DESCENDANTS_SQL, {"code": resolved.area_code}
        ).all()
    }
    scope = sorted(ancestors | descendants)

    now = datetime.now(UTC)
    rows = session.scalars(
        select(Outage)
        .where(
            Outage.resolved.is_(False),
            Outage.area_code.in_(scope),
            or_(Outage.end_time.is_(None), Outage.end_time >= now),
        )
        .order_by(Outage.severity.asc(), Outage.start_time.desc())
    ).all()

    payload, confirmed = [], False
    for outage in rows:
        covering = outage.area_code in ancestors
        confirmed = confirmed or covering
        payload.append({
            "area": outage.area,
            "region": outage.region,
            "area_code": outage.area_code,
            "scope": "covering" if covering else "partial",
            "affected_services": [
                s for s in (outage.affected_services or "").split(",") if s
            ],
            "severity": outage.severity,
            "cause": outage.cause,
            "description": _describe(outage, language),
            "start_time": (_aware(outage.start_time) or outage.start_time).isoformat() if outage.start_time else None,
            "eta": (_aware(outage.end_time) or outage.end_time).isoformat() if outage.end_time else None,
        })

    return {
        "area": area,
        "verified_area": resolved.name_fr,
        "area_code": resolved.area_code,
        "match": "exact" if resolved.exact else "approximate",
        "status": "incident" if payload else "operational",
        "coverage": ("confirmed" if confirmed else "partial") if payload else None,
        "verified": True,
        "outages": payload,
    }
