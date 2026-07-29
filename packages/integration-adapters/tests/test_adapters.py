"""Offline tests: factory defaults to live (P6); mock adapters honor the ports (no network)."""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest
from integration_adapters import get_billing_adapter, get_nms_adapter, get_ticketing_adapter

from domain_core.value_objects import IdempotencyKey, Money

os.environ.setdefault("CONNECTOR_MODE", "mock")


def test_factory_explicit_mock(monkeypatch) -> None:
    monkeypatch.setenv("CONNECTOR_MODE", "mock")
    assert type(get_billing_adapter()).__name__ == "MockBillingAdapter"


def test_live_without_url_raises(monkeypatch) -> None:
    """Live mode must fail loud when a URL is missing — never silently fake a money operation."""
    monkeypatch.setenv("CONNECTOR_MODE", "live")
    monkeypatch.delenv("BILLING_ADAPTER_URL", raising=False)
    from integration_adapters.factory import AdapterConfigError
    with pytest.raises(AdapterConfigError, match="CONNECTOR_MODE=live but BILLING_ADAPTER_URL is not set"):
        get_billing_adapter()


def test_mock_billing_charge_and_invoices() -> None:
    billing = get_billing_adapter()
    ref = asyncio.run(billing.charge("c1", Money(Decimal("42.500")), IdempotencyKey("abc1234567xyz")))
    assert ref.startswith("PAY-")
    assert asyncio.run(billing.get_open_invoices("c1")) == []


def test_mock_nms_and_ticketing() -> None:
    status = asyncio.run(get_nms_adapter().get_network_status("Tunis"))
    assert status["status"] == "unavailable"
    ticket = asyncio.run(get_ticketing_adapter().create_ticket("subj", "body", "high"))
    assert ticket.ticket_id.startswith("GLPI-")