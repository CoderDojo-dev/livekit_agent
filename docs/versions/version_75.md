# Version 75 — Policy Verdict Persistence Fix (JSONB Serialization)

> **Base branch:** `version_74`
> **Files changed:** 1 modified, 2 new (+policy-service tests + harness wiring)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| mcp dependency     | `mcp==1.29.0` (inherited from v73, unchanged) |

---

## The Bug

`policy-service` stores the evaluated context as a JSONB snapshot. `PolicyContext.model_dump()`
leaves `identity_expires_at` as a **`datetime`**, and psycopg refuses to serialize a `datetime`
into a JSONB column at the driver level — a failure `SQLAlchemyError` never sees.

The verdict path failed **exactly when it was about to authorize**: `identity_expires_at` is only
set after a successful verification, which is precisely when a sensitive action (`TOP_UP`,
`CHANGE_PLAN`, …) is approved. `_persist()` re-raises on `AUTHORIZED` (spec 12: no persisted
verdict, no execution), so every authorized sensitive action returned **HTTP 500** and the
agent-worker, failing closed, escalated it to a manager. The measured escalation rate was
therefore describing this defect rather than the agent's behaviour.

---

## Fixes Applied

### 1. JSON-serializable snapshot (`service.py`)
`inputs=ctx.model_dump()` → `inputs=ctx.model_dump(mode="json")` — datetimes are serialized
into ISO-8601 strings the driver can store. The verdict ledger now persists AUTHORIZED verdicts
instead of 500ing on the first identity-verified action.

### 2. Persistence guard widened to `Exception` (`service.py`)
`except SQLAlchemyError` → `except Exception` with `exc_info=True` logging. A storage defect
(driver-level serialization, connection, anything) must never silently rewrite a verdict — the
fail-closed contract stays: `AUTHORIZED` without a persisted verdict still raises, but now only
for genuine storage outages, not serialization details.

---

## Tests & Harness

- `services/policy-service/tests/conftest.py` (new): live-database fixture — the failure happens
  inside the psycopg driver, so an in-memory double would prove nothing. Each test runs in a
  rolled-back transaction, so the audited, append-only verdict ledger is never polluted.
- `services/policy-service/tests/test_verdict_persistence.py` (new): proves that an AUTHORIZED
  verdict with `identity_expires_at` set is now persisted (verdict id returned, row readable);
  the old code failed this test with a driver-level 500.
- `scripts/test_committed.ps1` (updated): policy-service src on `PYTHONPATH` + its suite added to
  the committed-tree run, so this regression class cannot return unnoticed.

---

## Validation

- policy-service suite: **17/17** green on the committed tree (business-api 24, agent-worker 74,
  notification-service 10 — all green).
- Live behaviour (rebuild not required for a pure code fix): the verified TOP_UP path now returns
  an AUTHORIZED verdict id instead of HTTP 500.

---

## Out of Scope (left open, unchanged)

- IdentityVerificationTask `GATE_TIMEOUT_S=40` > `TASK_DEADLINE_S=30`
- `knowledge_search` ToolError; escalation vocabulary duplication; `MAX_OFFERS=3` vs spec `2`
- `test_chaos_wiring.py` 5→4 tests; Twilio SIP (`SIP_TRANSFER_ENABLED`)
- Pre-existing ruff findings (F401/B905/RUF007/I001)
