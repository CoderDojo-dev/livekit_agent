"""Typed caller snapshot held in session user-data (spec section 4 / section 1 identity model).

Worker-side mirror of the context-service Customer360 response. Carries both canonical UUIDs
(customer_id, subscription_id) so downstream domain calls pass UUIDs, never the MSISDN.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CustomerContext:
    """The caller's pre-fetched profile, available to every persona and tool."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    subscription_id: str | None = None
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0
    glpi_user_id: int | None = None

    @classmethod
    def from_snapshot(cls, data: dict) -> CustomerContext:
        """Build from a context-service snapshot dict (ignores enrichment-only fields)."""
        return cls(
            customer_id=data["customer_id"],
            full_name=data["full_name"],
            msisdn=data["msisdn"],
            subscription_type=data["subscription_type"],
            subscription_id=data.get("subscription_id"),
            preferred_language=data.get("preferred_language", "fr"),
            is_vip=data.get("is_vip", False),
            fraud_suspected=data.get("fraud_suspected", False),
            account_age_days=data.get("account_age_days", 0),
            glpi_user_id=data.get("glpi_user_id"),
        )