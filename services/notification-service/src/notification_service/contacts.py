"""Contact resolution: customer_id -> (recipient handle, language) from crm.customers.

Centralizing this here is deliberate. Callers (ticketing, billing, future services) should only
know a customer_id and a template - never a phone number or email. The notification-service owns
the mapping from a customer to how they are reached, so contact details live in exactly one place
and every caller stays decoupled from PII.

Channel -> handle:
  whatsapp / sms -> crm.customers.contact_number (E.164)
  email          -> crm.customers.email

Language falls back to the customer's preferred_language when the caller did not force one.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class ContactUnavailable(RuntimeError):
    """No usable contact handle for this customer/channel. Surfaced honestly, never guessed."""


def _channel_handle(customer, channel: str) -> str | None:
    if channel in ("whatsapp", "sms"):
        return customer.contact_number
    if channel == "email":
        return customer.email
    return None


def resolve_recipient(customer_id: str, channel: str) -> tuple[str, str | None]:
    """Return (handle, preferred_language) for a customer on a channel.

    Raises ContactUnavailable when the DB is not configured, the customer is unknown, or the
    customer has no handle for that channel - so the send fails honestly instead of addressing
    a UUID.
    """
    if not os.getenv("DATABASE_URL"):
        raise ContactUnavailable("contact lookup unavailable: DATABASE_URL not configured")

    from persistence.engine import session_scope
    from persistence.models.crm import Customer
    from persistence.util import to_uuid

    cid = to_uuid(customer_id)
    if cid is None:
        raise ContactUnavailable(f"{customer_id!r} is not a valid customer id")

    try:
        with session_scope() as session:
            customer = session.get(Customer, cid)
            if customer is None:
                raise ContactUnavailable(f"no customer {customer_id}")
            handle = _channel_handle(customer, channel)
            language = customer.preferred_language
    except ContactUnavailable:
        raise
    except Exception as exc:
        raise ContactUnavailable(f"contact lookup failed: {exc}") from exc

    if not handle:
        field = "email" if channel == "email" else "contact_number"
        raise ContactUnavailable(f"customer {customer_id} has no {field} for channel {channel!r}")
    return handle, language
