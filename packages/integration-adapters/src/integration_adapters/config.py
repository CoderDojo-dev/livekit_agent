"""Adapter mode + endpoint resolution (spec section 16.6): mock by default, live via env."""
from __future__ import annotations

import os


def connector_mode() -> str:
    """'mock' (local) or 'live' (real legacy systems). Defaults to mock."""
    return os.getenv("CONNECTOR_MODE", "mock").strip().lower()


def is_live() -> bool:
    return connector_mode() == "live"


def adapter_url(name: str) -> str | None:
    """Base URL for a live adapter, e.g. adapter_url('billing') -> BILLING_ADAPTER_URL."""
    return os.getenv(f"{name.upper()}_ADAPTER_URL")