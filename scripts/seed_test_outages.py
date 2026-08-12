"""Pannes de demonstration pour Gafsa, Sousse et Monastir.

Donnees de TEST. Refuse de s'executer sans ALLOW_TEST_DATA=1.
Idempotent : une panne ouverte de meme zone et meme cause n'est pas dupliquee.

Usage :
    ALLOW_TEST_DATA=1 python3 scripts/seed_test_outages.py
    ALLOW_TEST_DATA=1 python3 scripts/seed_test_outages.py --purge
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.oss import Outage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_test_outages")

NOW = datetime.now(UTC)


def _at(hours: float) -> datetime:
    return NOW + timedelta(hours=hours)


# (area_code, region, area, services, severity, cause,
#  description_fr, description_en, start, end, resolved)
ROWS = [
    (
        "TN-71-METLAOUI", "Gafsa", "Metlaoui", "mobile,data", "major", "fiber_cut",
        "Coupure de fibre optique sur la liaison Metlaoui - Gafsa suite a des "
        "travaux de voirie. Les appels et l'internet mobile sont degrades dans la "
        "delegation de Metlaoui.",
        "Fiber cut on the Metlaoui - Gafsa link caused by roadworks. Calls and "
        "mobile internet are degraded in the Metlaoui delegation.",
        _at(-3), _at(2), False,
    ),
    (
        "TN-51", "Sousse", "Sousse", "data,fixe", "critical", "equipment_failure",
        "Defaillance d'un equipement d'agregation regional. L'internet fixe et les "
        "donnees mobiles sont interrompus sur l'ensemble du gouvernorat de Sousse. "
        "Les equipes techniques sont sur site.",
        "Regional aggregation equipment failure. Fixed internet and mobile data "
        "are down across the whole Sousse governorate. Field teams are on site.",
        _at(-1), None, False,
    ),
    (
        "TN-52-KSAR-HELLAL", "Monastir", "Ksar Hellal", "fixe", "minor",
        "planned_maintenance",
        "Maintenance planifiee du central telephonique de Ksar Hellal. "
        "Interruption breve du service fixe, retablissement progressif.",
        "Planned maintenance on the Ksar Hellal exchange. Brief fixed-line "
        "interruption with progressive restoration.",
        _at(-0.5), _at(1.5), False,
    ),
    (
        "TN-71-REDEYEF", "Gafsa", "Redeyef", "mobile", "major", "power_failure",
        "Coupure d'alimentation electrique sur le site de Redeyef.",
        "Power outage at the Redeyef site.",
        _at(-30), _at(-26), True,
    ),
    (
        "TN-52-JEMMAL", "Monastir", "Jemmal", "data", "minor", "congestion",
        "Congestion temporaire sur la cellule de Jemmal.",
        "Temporary congestion on the Jemmal cell.",
        _at(-5), _at(-1), False,
    ),
    (
        None, "Sfax", None, "mobile", "critical", "equipment_failure",
        "Panne sans zone renseignee, heritee de l'ancien systeme.",
        "Outage with no area recorded, inherited from the legacy system.",
        _at(-8), None, False,
    ),
    (
        "TN-51-MSAKEN", "Sousse", "Msaken", "mobile,data,fixe", "major",
        "third_party_damage",
        "Cable endommage par un engin de chantier tiers a l'entree de Msaken. "
        "Reparation en cours, retablissement estime dans la journee.",
        None,
        _at(-2), _at(6), False,
    ),
    (
        "TN-52-MOKNINE", "Monastir", "Moknine", "mobile", "minor", None,
        None, None,
        _at(-1.5), None, False,
    ),
    (
        "TN-71-GAFSA-NORD", "Gafsa", "Gafsa Nord", "data", "minor", "weather",
        "Degradation du debit data liee aux fortes chaleurs sur le site de Gafsa "
        "Nord. Surveillance active.",
        "Data throughput degradation caused by extreme heat at the Gafsa Nord "
        "site. Under active monitoring.",
        _at(-4), None, False,
    ),
]

DEMO_CODES = [r[0] for r in ROWS if r[0]]


def purge() -> None:
    with session_scope() as session:
        rows = session.scalars(
            select(Outage).where(Outage.area_code.in_(DEMO_CODES))
        ).all()
        for row in rows:
            session.delete(row)
        logger.info("%d pannes de demonstration supprimees", len(rows))


def seed() -> None:
    inserted, skipped = 0, 0
    with session_scope() as session:
        for (code, region, area, services, severity, cause,
             d_fr, d_en, start, end, resolved) in ROWS:
            existing = session.scalars(
                select(Outage).where(
                    Outage.area_code == code,
                    Outage.cause == cause,
                    Outage.resolved.is_(False),
                )
            ).first()
            if existing is not None and code is not None:
                skipped += 1
                continue
            session.add(Outage(
                region=region,
                area=area,
                area_code=code,
                affected_services=services,
                severity=severity,
                cause=cause,
                description_fr=d_fr,
                description_en=d_en,
                start_time=start,
                end_time=end,
                resolved=resolved,
            ))
            inserted += 1
    logger.info("pannes inserees=%d ignorees=%d", inserted, skipped)


if __name__ == "__main__":
    if os.getenv("ALLOW_TEST_DATA") != "1":
        logger.error(
            "Refus : ces donnees sont des donnees de test. "
            "Relancer avec ALLOW_TEST_DATA=1 si c'est bien voulu."
        )
        sys.exit(2)
    if "--purge" in sys.argv:
        purge()
    else:
        seed()
