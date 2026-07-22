"""Adapter factory: CONNECTOR_MODE + the adapter URL decide mock vs live (spec section 16.6).

Live mode does NOT fall back to mock: if CONNECTOR_MODE=live but an adapter's URL is missing, the
factory raises. A money operation must never be silently faked - a customer told "payment done,
ref X" when nothing moved is worse than an honest failure. Mock is reachable only when
CONNECTOR_MODE=mock is explicitly selected (local dev / CI).
"""
from __future__ import annotations

from domain_core.ports.balance import BalancePort
from domain_core.ports.billing import BillingPort
from domain_core.ports.crm import CrmPort
from domain_core.ports.nms import NmsPort
from domain_core.ports.payment import PaymentPort
from domain_core.ports.provisioning import ProvisioningPort
from domain_core.ports.ticketing import TicketingPort
from integration_adapters.billing_adapter import LiveBillingAdapter, MockBillingAdapter
from integration_adapters.config import adapter_url, is_live
from integration_adapters.crm_adapter import LiveCrmAdapter, MockCrmAdapter
from integration_adapters.glpi_adapter import LiveGlpiAdapter, MockGlpiAdapter
from integration_adapters.nms_adapter import LiveNmsAdapter, MockNmsAdapter
from integration_adapters.ocs_adapter import LiveOcsAdapter, MockOcsAdapter
from integration_adapters.payment_adapter import LivePaymentAdapter, MockPaymentAdapter
from integration_adapters.provisioning_adapter import (
    LiveProvisioningAdapter,
    MockProvisioningAdapter,
)


class AdapterConfigError(RuntimeError):
    """CONNECTOR_MODE=live but a required adapter URL is not configured. Never silently mocked."""


def _pick(name, live_cls, mock_cls):
    if is_live():
        url = adapter_url(name)
        if not url:
            raise AdapterConfigError(
                f"CONNECTOR_MODE=live but {name.upper()}_ADAPTER_URL is not set. Refusing to fall "
                f"back to the mock {name!r} adapter, which would fake a real operation."
            )
        return live_cls(url)
    return mock_cls()


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


def get_provisioning_adapter() -> ProvisioningPort:
    return _pick("provisioning", LiveProvisioningAdapter, MockProvisioningAdapter)


def get_ticketing_adapter() -> TicketingPort:
    return _pick("glpi", LiveGlpiAdapter, MockGlpiAdapter)