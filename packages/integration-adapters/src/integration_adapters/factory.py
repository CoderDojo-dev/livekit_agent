"""Adapter factory: CONNECTOR_MODE + the adapter URL decide mock vs live (spec section 16.6).

Falls back to mock if live is selected but no URL is configured - so a half-configured environment
degrades safely rather than crashing.
"""
from __future__ import annotations

from domain_core.ports.balance import BalancePort
from domain_core.ports.billing import BillingPort
from domain_core.ports.crm import CrmPort
from domain_core.ports.nms import NmsPort
from domain_core.ports.payment import PaymentPort
from domain_core.ports.ticketing import TicketingPort
from integration_adapters.billing_adapter import LiveBillingAdapter, MockBillingAdapter
from integration_adapters.config import adapter_url, is_live
from integration_adapters.crm_adapter import LiveCrmAdapter, MockCrmAdapter
from integration_adapters.glpi_adapter import LiveGlpiAdapter, MockGlpiAdapter
from integration_adapters.nms_adapter import LiveNmsAdapter, MockNmsAdapter
from integration_adapters.ocs_adapter import LiveOcsAdapter, MockOcsAdapter
from integration_adapters.payment_adapter import LivePaymentAdapter, MockPaymentAdapter


def _pick(name, live_cls, mock_cls):
    url = adapter_url(name)
    return live_cls(url) if (is_live() and url) else mock_cls()


def get_billing_adapter() -> BillingPort:
    return _pick("billing", LiveBillingAdapter, MockBillingAdapter)


def get_balance_adapter() -> BalancePort:
    return _pick("ocs", LiveOcsAdapter, MockOcsAdapter)


def get_payment_adapter() -> PaymentPort:
    return _pick("payment", LivePaymentAdapter, MockPaymentAdapter)


def get_crm_adapter() -> CrmPort:
    return _pick("crm", LiveCrmAdapter, MockCrmAdapter)


def get_nms_adapter() -> NmsPort:
    return _pick("nms", LiveNmsAdapter, MockNmsAdapter)


def get_ticketing_adapter() -> TicketingPort:
    return _pick("glpi", LiveGlpiAdapter, MockGlpiAdapter)