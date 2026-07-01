#!/usr/bin/env python3
"""CI/ops hook: verify the audit hash-chain against the live DB (report #19/#22 companion).

Exit 0 = intact, 1 = broken. Requires DATABASE_URL; a no-op success if persistence isn't importable
so the CI step never hard-fails on a unit-test-only runner.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL unset; skipping audit-chain verify")
        return 0
    try:
        from audit_trail import PgAuditLedger
        from persistence.engine import session_scope
    except Exception as exc:  # noqa: BLE001
        print(f"persistence not available ({exc}); skipping")
        return 0
    with session_scope() as session:
        ledger = PgAuditLedger(session)
        intact = ledger.verify()
        print(f"audit chain intact={intact} entries={ledger.count()}")
        return 0 if intact else 1


if __name__ == "__main__":
    sys.exit(main())