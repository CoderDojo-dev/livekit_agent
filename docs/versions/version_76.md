# Version 76 — Test Environment Hardening (Incident 4) + Validation Chain Consolidation

> **Base branch:** `version_75`
> **Files changed:** 4 modified/added, 1 deleted (+2 new reports)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| Docker Compose     | Unchanged (21 services, `livekit-server` v1.8.4 self-hosted profile untouched) |

---

## Context — Incident 4

The `SAWarning: transaction already deassociated` seen during policy-service tests is benign,
but it exposed an **implicit, undocumented guarantee**: `_persist()` calls
`self._session.commit()` of its own right, and the only thing that keeps that commit out of the
database is SQLAlchemy's default `join_transaction_mode="conditional_savepoint"`, which falls
back to `rollback_only` in our fixture layout. That fallback is what protects the
**append-only, hash-chained verdict ledger** — the one place in the system where a stray write
cannot be repaired — from being polluted by test verdicts. The guarantee worked by accident: a
SQLAlchemy upgrade that changed the default would silently commit test verdicts into the ledger.

A second, related defect: `scripts/test_committed.ps1` pinned `PYTHONPATH` but not
`DATABASE_URL`, so the whole validation chain depended on whatever `DATABASE_URL` the invoking
shell happened to carry — a compose hostname instead of `localhost` would fail the 17
policy-service tests on a healthy branch, for an environment reason. That is exactly how this
defect survived five versions (no skip mechanism; the tests stayed honest, the environment did
not).

---

## Changes Applied

### 1. `services/policy-service/tests/conftest.py` — explicit transaction join mode
```python
session = Session(bind=connection, future=True, join_transaction_mode="rollback_only")
```
plus an explanatory comment. One line, **no behaviour change** — it pins the guarantee that
already existed implicitly instead of relying on an undocumented SQLAlchemy default.

### 2. `scripts/test_committed.ps1` — pinned `DATABASE_URL`
`DATABASE_URL` is now set next to `PYTHONPATH`
(`postgresql+psycopg://telecom:telecom@localhost:5432/telecom`) and cleaned up in the `finally`
block. **No skip was added** if Postgres is unreachable: a test that disables itself is the
mechanism by which this defect survived five versions.

### 3. `scripts/test_committed.sh` — deleted
It was a stale maintenance duplicate (3 suites only, no policy-service src on `PYTHONPATH`, no
`DATABASE_URL` pin) and unusable on this machine (no bash/WSL). The `.ps1` script is now the
single canonical validation entry point, documented in the `README`.

### 4. `README.md` — validation section
Documents `scripts/test_committed.ps1` as the canonical validation command (all four suites
against the committed tree, pinned `PYTHONPATH` + `DATABASE_URL`, Windows PowerShell, no
WSL/git-bash required).

---

## Proof — What Was Measured (not deduced)

- **Green under hostile conditions (pin + hostile shell):** full chain on the committed tree,
  with a hostile `DATABASE_URL` (`postgres` compose hostname, unreachable from the host)
  injected in the invoking shell → **125/125 PASS** (24 business-api + 74 agent-worker + 10
  notification-service + 17 policy-service). The pin overrides the inherited environment.
- **Real red (pin removed, hostile env kept):** 7 connection errors (5 business-api + 2
  policy), 118 passed, exit code 0 — without the pin, the hostile `DATABASE_URL` reaches the
  suites and breaks the chain.
- **Ledger integrity:** `policy.policy_verdicts=2`, `audit.audit_ledger=44`,
  `conversation.callback_schedules=4` — identical before and after every test execution. No
  test verdict ever reaches the append-only ledger (`rollback_only` verified).
- **SAWarning:** 17/17 pass even with `-W error::sqlalchemy.exc.SAWarning`. The warning may
  still appear on runs where a verdict fails to persist (it comes from `rollback()` after a
  raised `_persist()`) — that is not a regression signal.

---

## Validation

- policy-service suite: **17/17** green on the committed tree with the pinned mode.
- Full chain `test_committed.ps1 -Ref HEAD` (committed tree `a21a493`): **125/125 PASS**.
- Live: `policy-service` container healthy, `GET /health` → `{"status":"ok"}`; no rebuild
  required (no production code changed).
- `POLICY_UNAVAILABLE` occurrences in agent-worker logs: **0** — recorded, but NOT
  interpreted as a proof (containers were recreated; the only traffic since is the recipe). The
  real control is the §7 query over a real call day — left open.

---

## Out of Scope (left open, unchanged)

- The §7 real-traffic control (requires a real call day, not available at patch time).
- All items previously listed as out of scope in v75 (identity verification timings, Twilio
  SIP, pre-existing ruff findings, etc.).
