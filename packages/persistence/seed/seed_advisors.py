"""Seed the dev advisor (idempotent).

One advisor covering every skill, marked available and on-call, so both escalation branches can be
exercised end to end: a live SIP transfer rings this number, and a scheduled callback notifies the
same person on WhatsApp/email.

Run:  python -m seed.seed_advisors
"""
from __future__ import annotations

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.routing import Advisor

ADVISORS = [
    {
        "full_name": "Chouaib Saad",
        "email": "choiyebsaad2000@gmail.com",
        "phone_e164": "+21626078277",
        "skills": "general,billing,technical,account",
        "language": "fr",
        "status": "available",
        "max_concurrent_calls": 1,
        "is_on_call": True,
        "is_active": True,
    },
]


def seed() -> None:
    added = 0
    with session_scope() as session:
        for row in ADVISORS:
            existing = session.scalar(
                select(Advisor).where(Advisor.phone_e164 == row["phone_e164"])
            )
            if existing is not None:
                for field, value in row.items():
                    setattr(existing, field, value)
                print(f"  updated {row['full_name']} ({row['phone_e164']})")
                continue
            session.add(Advisor(**row))
            added += 1
            print(f"  added {row['full_name']} ({row['phone_e164']}) skills={row['skills']}")
    print(f"ADVISORS_SEEDED added={added}")


if __name__ == "__main__":
    seed()