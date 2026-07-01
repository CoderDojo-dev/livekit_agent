"""Audit wiring: one hash-chained ledger per execution-service process."""
from __future__ import annotations

from functools import lru_cache

from audit_trail import AuditLedger


@lru_cache
def get_ledger() -> AuditLedger:
    """Return the process-wide audit ledger."""
    return AuditLedger()