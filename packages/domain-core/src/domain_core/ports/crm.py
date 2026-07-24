"""Port to the CRM system of record (Blueprint section 7.2).

The full surface covers everything the system reads from CRM today, so switching from the mock
(context-service Postgres) to a live CRM later is config, not redesign.

Design rule that matters most: "unknown customer" and "CRM unreachable" never collapse.
A 404 -> None / [] ; a 5xx or connection failure -> raises ``CrmUnavailable``. Without that split,
the agent would tell a caller "I have no account for this number" during a CRM outage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from domain_core.entities import Client


class CrmUnavailable(RuntimeError):
    """The CRM could not be reached or returned a server error.

    Distinct from "unknown customer" (404 -> None) so the agent never mistakes an outage for a
    customer-not-found and tells the caller their account does not exist.
    """


@dataclass(slots=True)
class ContactInfo:
    """Where to reach a customer (notification routing)."""

    phone: str | None = None
    email: str | None = None
    preferred_language: str = "fr"


@dataclass(slots=True)
class SubscriptionLine:
    """One line on the customer's account."""

    subscription_id: str
    msisdn: str
    plan: str
    status: str
    roaming_enabled: bool = False


@dataclass(slots=True)
class Customer360:
    """The full snapshot the agent opens with - composed from client + contact + subscriptions.

    Either the CRM returns this in one call, or we compose it from the parts; the object is the
    same either way so callers do not care which path produced it.
    """

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: str = "fr"
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0
    subscriptions: list[SubscriptionLine] = field(default_factory=list)


class CrmPort(ABC):
    """Resolve and read customer profiles from the CRM."""

    @abstractmethod
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        """Return the client owning ``msisdn`` or None if unknown."""

    @abstractmethod
    async def get_client_by_id(self, customer_id: str) -> Client | None:
        """Return the client with ``customer_id`` or None if unknown."""

    @abstractmethod
    async def get_contact(self, customer_id: str) -> ContactInfo | None:
        """Return contact routing info (phone/email/language) or None if unknown."""

    @abstractmethod
    async def get_subscriptions(self, customer_id: str) -> list[SubscriptionLine]:
        """Return the customer's lines (plan, status, roaming). Empty list if unknown."""

    @abstractmethod
    async def get_customer_360(self, customer_id: str) -> Customer360 | None:
        """Return the full 360 snapshot, or None if the customer is unknown.

        If the CRM exposes a single 360 endpoint, use it directly; otherwise compose from
        client + contact + subscriptions. Either path returns the same object.
        """

    @abstractmethod
    async def set_external_reference(self, customer_id: str, key: str, value: str) -> bool:
        """Write-back a linkage (e.g. glpi_user_id). Returns True on success."""