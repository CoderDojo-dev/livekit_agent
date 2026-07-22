"""Adapters: one module per legacy system, each implementing exactly one domain-core port.

A vendor API change has a one-module blast radius (Blueprint ADR 5.4). Mock by default; live via
CONNECTOR_MODE + the adapter URL (spec section 16.6).
"""
from integration_adapters.factory import (
    get_balance_adapter,
    get_billing_adapter,
    get_crm_adapter,
    get_nms_adapter,
    get_payment_adapter,
    get_provisioning_adapter,
    get_ticketing_adapter,
)

__all__ = [
    "get_balance_adapter",
    "get_billing_adapter",
    "get_crm_adapter",
    "get_nms_adapter",
    "get_payment_adapter",
    "get_provisioning_adapter",
    "get_ticketing_adapter",
]