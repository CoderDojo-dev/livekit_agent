# Version 47 — Ruff/Mypy Cleanup, OCS-billing-sim Container & Adapter Hardening

## What's new
- **CI hardening**: ruff/mypy now FAIL on errors (removed `|| true` masking)
- **67 files linted**: import ordering, `setattr()` → direct attr access, `object` → `Any`, `zip(strict=False)`, unused imports, inline module imports consolidated
- **New `ocs-billing-sim` container** (Postgres-backed OCS/billing simulator), port 8109:8107
- **Adapter factory hardening**: `_pick()` raises `AdapterConfigError` when `CONNECTOR_MODE=live` but adapter URL is missing — no silent mock fallback for money operations (billing/ocs/payment)
