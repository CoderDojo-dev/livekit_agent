"""Typed caller snapshot held in session user-data (Blueprint section 4.3).

Worker-side mirror of the context-service Customer360 response. Keeping it here decouples
the session from the service's wire schema.
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
    preferred_language: str = "fr"
    is_vip: bool = False
    account_age_days: int = 0

    @classmethod
    def from_snapshot(cls, data: dict) -> "CustomerContext":
        """Build from a context-service snapshot dict (ignores enrichment fields)."""
        return cls(
            customer_id=data["customer_id"],
            full_name=data["full_name"],
            msisdn=data["msisdn"],
            subscription_type=data["subscription_type"],
            preferred_language=data.get("preferred_language", "fr"),
            is_vip=data.get("is_vip", False),
            account_age_days=data.get("account_age_days", 0),
        )