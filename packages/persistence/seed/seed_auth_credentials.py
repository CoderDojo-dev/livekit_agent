"""Backfill protected CIN-last-four verifiers for existing customers."""
from __future__ import annotations

import hashlib
import hmac
import os

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.auth import CustomerCredential
from persistence.models.crm import Customer


def digest(customer_id: str, last_four: str, key: str) -> str:
    message = (
        f"cin_last4:{customer_id}:{last_four}"
    ).encode()
    return hmac.new(
        key.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def seed() -> None:
    key = os.environ.get("AUTH_CIN_HMAC_KEY", "")
    if len(key) < 32:
        raise RuntimeError(
            "AUTH_CIN_HMAC_KEY must contain at least 32 characters"
        )

    inserted = 0
    with session_scope() as session:
        customers = list(session.scalars(select(Customer)))

        for customer in customers:
            existing = session.scalar(
                select(CustomerCredential).where(
                    CustomerCredential.customer_id == customer.id,
                    CustomerCredential.verifier_type == "cin_last4",
                )
            )
            if existing is not None:
                continue

            normalized = "".join(
                char
                for char in customer.national_id
                if char.isdigit()
            )
            if len(normalized) < 4:
                raise RuntimeError(
                    f"Customer {customer.id} has invalid CIN data"
                )

            session.add(
                CustomerCredential(
                    customer_id=customer.id,
                    verifier_type="cin_last4",
                    verifier_digest=digest(
                        str(customer.id),
                        normalized[-4:],
                        key,
                    ),
                    key_version=1,
                    active=True,
                )
            )
            inserted += 1

    print(f"seeded {inserted} protected CIN credentials")


if __name__ == "__main__":
    seed()
