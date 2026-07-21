"""Update the pilot customers' contact details in place (idempotent).

The main seed skips when customers already exist, so it will not refresh contact_number/email on
a database that was seeded earlier. This updates the three pilot customers' WhatsApp number and
email so notifications can reach a real, opt-in test handle - without wiping or re-seeding.
"""
from __future__ import annotations

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.crm import Customer

# national_id -> (contact_number, email). All three point at the verified test WhatsApp number;
# emails are the three real Mailtrap/Gmail inboxes.
PILOT_CONTACTS = {
    "11224087": ("+21626078277", "choiyebsaad2000@gmail.com"),      # Amine (primary test)
    "33449912": ("+21626078277", "chouaibsaad.contact@gmail.com"),  # Yousra
    "55662256": ("+21626078277", "ws0461646@gmail.com"),            # Karim
}


def sync() -> None:
    updated = 0
    with session_scope() as session:
        for national_id, (phone, email) in PILOT_CONTACTS.items():
            customer = session.scalar(select(Customer).where(Customer.national_id == national_id))
            if customer is None:
                print(f"  skip {national_id}: not found")
                continue
            customer.contact_number = phone
            customer.email = email
            updated += 1
            print(f"  {customer.first_name} {customer.last_name}: {phone} / {email}")
    print(f"PILOT_CONTACTS_SYNCED updated={updated}")


if __name__ == "__main__":
    sync()
