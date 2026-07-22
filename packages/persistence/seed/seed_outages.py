"""Seed a small set of network incidents into oss.outages (idempotent).

Gives the technical persona real incident data to answer "is there a known outage in my area?".
One active incident (with an ETA), one active incident without an ETA, and one already-resolved
record so the projection can be checked to correctly IGNORE resolved outages.

Run:  python -m seed.seed_outages
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.oss import Outage

NOW = datetime.now(UTC)

OUTAGES = [
    {
        "region": "Ariana",
        "area": "Ariana Ville",
        "affected_services": "mobile,data",
        "severity": "major",
        "start_time": NOW - timedelta(hours=3),
        "end_time": NOW + timedelta(hours=2),   # ETA the agent can quote
        "resolved": False,
    },
    {
        "region": "Sfax",
        "area": "Sfax Centre",
        "affected_services": "data",
        "severity": "minor",
        "start_time": NOW - timedelta(hours=1),
        "end_time": None,                        # no ETA yet
        "resolved": False,
    },
    {
        "region": "Tunis",
        "area": "Tunis Centre",
        "affected_services": "mobile",
        "severity": "critical",
        "start_time": NOW - timedelta(days=2),
        "end_time": NOW - timedelta(days=1),
        "resolved": True,                        # must NOT be reported
    },
]


def seed() -> None:
    added = 0
    with session_scope() as session:
        for row in OUTAGES:
            exists = session.scalar(
                select(Outage).where(
                    Outage.area == row["area"], Outage.start_time == row["start_time"]
                )
            )
            if exists is not None:
                continue
            session.add(Outage(**row))
            added += 1
            state = "resolved" if row["resolved"] else "active"
            print(f"  {row['area']} ({row['severity']}, {state})")
    print(f"OUTAGES_SEEDED added={added}")


if __name__ == "__main__":
    seed()
