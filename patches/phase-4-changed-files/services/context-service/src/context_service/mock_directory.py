"""Seeded mock telco directory for the pilot (CDC mandates mock telco data).

This is the service's data source until a real CRM adapter (CrmPort) replaces it. It holds
the identity secret (last 4 digits of the national ID) which is checked server-side and
never returned in a Customer360 snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockCustomer:
    """A seeded customer record, including the server-side identity secret."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: str
    is_vip: bool
    account_age_days: int
    id_last4: str  # identity secret — never serialized into a snapshot


def _normalize(msisdn: str) -> str:
    return msisdn.strip().replace(" ", "")


_CUSTOMERS: dict[str, MockCustomer] = {
    "+21620155320": MockCustomer(
        customer_id="TT-100021",
        full_name="Amine Ben Salah",
        msisdn="+21620155320",
        subscription_type="Postpaid Flexi",
        preferred_language="fr",
        is_vip=False,
        account_age_days=1420,
        id_last4="4087",
    ),
    "+21629744108": MockCustomer(
        customer_id="TT-100045",
        full_name="Yousra Trabelsi",
        msisdn="+21629744108",
        subscription_type="Prepaid Mobile",
        preferred_language="ar",
        is_vip=True,
        account_age_days=305,
        id_last4="9912",
    ),
    "+21652310977": MockCustomer(
        customer_id="TT-100078",
        full_name="Karim Gharbi",
        msisdn="+21652310977",
        subscription_type="Fibre Fixe",
        preferred_language="en",
        is_vip=False,
        account_age_days=88,
        id_last4="2256",
    ),
}

_BY_ID: dict[str, MockCustomer] = {c.customer_id: c for c in _CUSTOMERS.values()}


def find_by_msisdn(msisdn: str) -> MockCustomer | None:
    """Return the customer owning ``msisdn`` or None."""
    return _CUSTOMERS.get(_normalize(msisdn))


def find_by_id(customer_id: str) -> MockCustomer | None:
    """Return the customer with ``customer_id`` or None."""
    return _BY_ID.get(customer_id)