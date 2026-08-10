"""Bootstrap the staff login. Idempotent: creates IF ABSENT, never overwrites.

Run once after migrating:

    docker compose -f infra/docker-compose/docker-compose.apps.yml \\
        exec business-api python -m business_api.seed_admin

Why this lives in business-api and not packages/persistence/seed/ (where the other five seeds
live): the scrypt hasher is business_api.infrastructure.auth.passwords, and persistence must not
depend on an app. Duplicating a password hasher to satisfy a directory convention would fork a
security primitive - the worse of the two trade-offs.

Why ADMIN_PASSWORD is never re-applied: after the first run the hash lives in the database and
the operator can change it in the product (POST /api/v1/auth/password). Overwriting on every boot
would silently undo that.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from business_api.infrastructure.auth import passwords
from persistence import session_scope
from persistence.models.portal_identity import STAFF_ROLES, PortalAccount


def main() -> int:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    role = os.getenv("ADMIN_ROLE", "administrateur").strip()

    if not email or not password:
        print("ADMIN_EMAIL and ADMIN_PASSWORD must be set", file=sys.stderr)
        return 2
    if role not in STAFF_ROLES:
        print(f"ADMIN_ROLE must be one of {', '.join(STAFF_ROLES)}", file=sys.stderr)
        return 2
    if len(password) < 10:
        print("ADMIN_PASSWORD must be at least 10 characters", file=sys.stderr)
        return 2

    with session_scope() as session:
        existing = session.scalar(
            select(PortalAccount).where(PortalAccount.email == email)
        )
        if existing is not None:
            print(f"admin already present: {email} ({existing.role}) - left untouched")
            return 0

        algorithm, params, encoded = passwords.hash_password(password)
        session.add(
            PortalAccount(
                kind="staff",
                email=email,
                password_hash=encoded,
                password_algo=algorithm,
                password_params=params,
                role=role,
                customer_id=None,
                is_active=True,
                password_changed_at=datetime.now(UTC),
            )
        )
        print(f"seeded staff account {email} ({role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())