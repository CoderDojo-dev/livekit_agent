"""Client-portal writes. The mirror of me_reads: scoped by the TOKEN, never by the URL.

Only one field is writable from the portal today — the customer's preferred
language — and it is deliberately narrow. `crm.customers` carries identity and
commercial data that a customer must not be able to edit from a browser, so
this module exposes one function per writable field rather than a generic
patch.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from persistence.models.crm import Customer

logger = logging.getLogger(__name__)

# Mirrors the crm.customers CHECK constraint (`preferred_language IN
# ('fr','ar','en')`, persistence/models/crm.py) and agents/domains.py's
# SUPPORTED_LANGUAGES. Validating here turns a would-be 500 from the constraint
# into a 400 that names the problem. The agent worker re-validates the stored
# value independently at session start (config/language_policy.py), so an
# unsupported value could never start a call in an unsupported language even if
# it reached the column by another route.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("fr", "ar", "en")


class UnsupportedLanguage(ValueError):
    """Raised for a language the platform has no STT/TTS preset for."""


def normalise_language(value: str | None) -> str:
    """Reduce a raw language value to a supported bare ISO-639-1 subtag.

    Accepts 'fr', 'FR', 'fr-FR', 'fr_FR', ' fr '. Mirrors
    agent-worker config/language_policy.normalise so the two ends of the
    pipeline agree on what a language value is.
    """
    subtag = str(value or "").strip().lower().replace("_", "-").split("-")[0]
    if subtag not in SUPPORTED_LANGUAGES:
        raise UnsupportedLanguage(
            f"language must be one of {', '.join(SUPPORTED_LANGUAGES)}"
        )
    return subtag


def set_preferred_language(session: Session, customer_id: UUID, language: str) -> dict:
    """Persist the caller's preferred agent language on their own CRM row.

    Returns the previous and current values so the endpoint can audit the
    change and so a no-op is distinguishable from a real edit.
    """
    code = normalise_language(language)
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise LookupError("customer not found")

    previous = customer.preferred_language
    customer.preferred_language = code
    session.flush()
    logger.info("preferred_language %s -> %s for customer %s", previous, code, customer_id)
    return {"preferred_language": code, "previous": previous, "changed": previous != code}
