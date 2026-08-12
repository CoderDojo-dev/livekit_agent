"""CRM adapter implementing CrmPort (report #3). In mock mode CRM reads come from Postgres
(context-service); this adapter is the *live* CRM binding.

Design rule enforced here: "unknown customer" and "CRM unreachable" never collapse.
A 404 -> None / [] ; a 5xx or connection failure -> raises ``CrmUnavailable``.
Without that split, the agent would tell a caller "I have no account for this number"
during a CRM outage.
"""
from __future__ import annotations

import httpx

from domain_core.entities import Client
from domain_core.ports.crm import (
    ContactInfo,
    CrmPort,
    CrmUnavailable,
    Customer360,
    SubscriptionLine,
)

_TIMEOUT = 8.0


def _to_client(data: dict) -> Client:
    return Client(
        customer_id=data["customer_id"], full_name=data.get("full_name", ""),
        msisdn=data.get("msisdn", ""), subscription_type=data.get("subscription_type", ""),
    )


def _to_contact(data: dict) -> ContactInfo:
    return ContactInfo(
        phone=data.get("phone") or data.get("contact_number"),
        email=data.get("email"),
        preferred_language=data.get("preferred_language", "fr"),
    )


def _to_subscription(data: dict) -> SubscriptionLine:
    return SubscriptionLine(
        subscription_id=data.get("subscription_id", ""),
        msisdn=data.get("msisdn", ""),
        plan=data.get("plan") or data.get("plan_code") or data.get("plan_type", ""),
        status=data.get("status", ""),
        roaming_enabled=data.get("roaming_enabled", False),
    )


def _to_360(data: dict) -> Customer360:
    subs = [_to_subscription(s) for s in data.get("subscriptions", [])]
    if not subs and data.get("subscription_id"):
        subs = [SubscriptionLine(
            subscription_id=data["subscription_id"], msisdn=data.get("msisdn", ""),
            plan=data.get("subscription_type", ""), status=data.get("status", "ACTIVE"),
            roaming_enabled=data.get("roaming_enabled", False),
        )]
    return Customer360(
        customer_id=data["customer_id"],
        full_name=data.get("full_name", ""),
        msisdn=data.get("msisdn", ""),
        subscription_type=data.get("subscription_type", ""),
        preferred_language=data.get("preferred_language", "fr"),
        is_vip=data.get("is_vip", False),
        fraud_suspected=data.get("fraud_suspected", False),
        account_age_days=data.get("account_age_days", 0),
        subscriptions=subs,
    )


def _classify_not_found(base_url: str, path: str, params: dict | None = None) -> dict | None:
    """Synchronous helper - not used (async path below is the live one). Kept for clarity."""


async def _get_or_raise(base_url: str, path: str, params: dict | None = None) -> dict | None:
    """GET from CRM: 404 -> None, 5xx or connection error -> CrmUnavailable."""
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
            resp = await client.get(path, params=params)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as exc:
        raise CrmUnavailable(f"CRM unreachable: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise CrmUnavailable(f"CRM server error {exc.response.status_code}") from exc
        raise CrmUnavailable(f"CRM unexpected status {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise CrmUnavailable(f"CRM request failed: {exc}") from exc


async def _post_or_raise(base_url: str, path: str, payload: dict) -> dict:
    """POST to CRM: 5xx or connection error -> CrmUnavailable."""
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT) as client:
            resp = await client.post(path, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as exc:
        raise CrmUnavailable(f"CRM unreachable: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise CrmUnavailable(f"CRM server error {exc.response.status_code}") from exc
        raise CrmUnavailable(f"CRM unexpected status {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise CrmUnavailable(f"CRM request failed: {exc}") from exc


class MockCrmAdapter(CrmPort):
    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        return None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        return None

    async def get_contact(self, customer_id: str) -> ContactInfo | None:
        return None

    async def get_subscriptions(self, customer_id: str) -> list[SubscriptionLine]:
        return []

    async def get_customer_360(self, customer_id: str) -> Customer360 | None:
        return None

    async def set_external_reference(self, customer_id: str, key: str, value: str) -> bool:
        return False


class LiveCrmAdapter(CrmPort):
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get_client_by_msisdn(self, msisdn: str) -> Client | None:
        data = await _get_or_raise(self._base, "/clients", {"msisdn": msisdn})
        return _to_client(data) if data else None

    async def get_client_by_id(self, customer_id: str) -> Client | None:
        data = await _get_or_raise(self._base, f"/clients/{customer_id}")
        return _to_client(data) if data else None

    async def get_contact(self, customer_id: str) -> ContactInfo | None:
        data = await _get_or_raise(self._base, f"/clients/{customer_id}/contact")
        return _to_contact(data) if data else None

    async def get_subscriptions(self, customer_id: str) -> list[SubscriptionLine]:
        data = await _get_or_raise(self._base, f"/clients/{customer_id}/subscriptions")
        if data is None:
            return []
        return [_to_subscription(s) for s in data.get("subscriptions", [])]

    async def get_customer_360(self, customer_id: str) -> Customer360 | None:
        # Try the dedicated 360 endpoint first; if it 404s, compose from client + contact + subs
        # (the object is the same either way).
        data = await _get_or_raise(self._base, f"/clients/{customer_id}/360")
        if data is not None:
            return _to_360(data)
        client = await self.get_client_by_id(customer_id)
        if client is None:
            return None
        contact = await self.get_contact(customer_id)
        subs = await self.get_subscriptions(customer_id)
        return Customer360(
            customer_id=client.customer_id,
            full_name=client.full_name,
            msisdn=client.msisdn,
            subscription_type=client.subscription_type,
            preferred_language=contact.preferred_language if contact else "fr",
            is_vip=client.is_vip,
            fraud_suspected=client.fraud_suspected,
            account_age_days=client.account_age_days,
            subscriptions=subs,
        )

    async def set_external_reference(self, customer_id: str, key: str, value: str) -> bool:
        try:
            await _post_or_raise(
                self._base, f"/clients/{customer_id}/external-reference",
                {"key": key, "value": value},
            )
            return True
        except CrmUnavailable:
            return False