"""Offline tests: factory defaults to mock; mock adapters honor the ports (no network)."""
from __future__ import annotations

import asyncio
from decimal import Decimal

from domain_core.value_objects import IdempotencyKey, Money

from integration_adapters import get_billing_adapter, get_nms_adapter, get_ticketing_adapter


def test_factory_defaults_to_mock(monkeypatch) -> None:
    monkeypatch.delenv("CONNECTOR_MODE", raising=False)
    assert type(get_billing_adapter()).__name__ == "MockBillingAdapter"


def test_live_without_url_falls_back_to_mock(monkeypatch) -> None:
    monkeypatch.setenv("CONNECTOR_MODE", "live")
    monkeypatch.delenv("BILLING_ADAPTER_URL", raising=False)
    assert type(get_billing_adapter()).__name__ == "MockBillingAdapter"


def test_mock_billing_charge_and_invoices() -> None:
    billing = get_billing_adapter()
    ref = asyncio.run(billing.charge("c1", Money(Decimal("42.500")), IdempotencyKey("abc1234567xyz")))
    assert ref.startswith("PAY-")
    assert asyncio.run(billing.get_open_invoices("c1")) == []


def test_mock_nms_and_ticketing() -> None:
    status = asyncio.run(get_nms_adapter().get_network_status("Tunis"))
    assert status["status"] == "operational"
    ticket = asyncio.run(get_ticketing_adapter().create_ticket("subj", "body", "high"))
    assert ticket.ticket_id.startswith("GLPI-")