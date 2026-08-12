"""Rattache les pannes existantes a une zone canonique (suite de la migration 0015).

Les lignes non resolubles sont LISTEES, jamais devinees : une zone douteuse doit
etre corrigee par l'exploitant, pas rattrapee par une approximation silencieuse.
"""
from __future__ import annotations

import logging

from nms_sim.geo_resolver import resolve
from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.oss import Outage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_area_code")


def run() -> None:
    resolved_count = 0
    unresolved: list[tuple[str, str | None, str | None]] = []

    with session_scope() as session:
        pending = session.scalars(
            select(Outage).where(Outage.area_code.is_(None))
        ).all()

        for outage in pending:
            for candidate in (outage.area, outage.region):
                if not candidate:
                    continue
                match = resolve(session, candidate)
                if match is not None:
                    outage.area_code = match.area_code
                    resolved_count += 1
                    break
            else:
                unresolved.append((str(outage.id), outage.area, outage.region))

    logger.info("backfilled %d outages", resolved_count)
    if unresolved:
        logger.warning(
            "%d outages could NOT be resolved and are now invisible to the agent "
            "until an operator fixes their zone:", len(unresolved)
        )
        for outage_id, area, region in unresolved:
            logger.warning("  id=%s area=%r region=%r", outage_id, area, region)


if __name__ == "__main__":
    run()
