# Version 53 — Postgres-backed Provisioning Ledger, CRM Port Expansion & Adapter Rewrites

> **Base branch:** `version_52`
> **Commit range:** version_52..version_53
> **Files changed:** 17 (+664 / -264)

---

## Containers & SDK

| Item                | Change                                                                 |
|---------------------|------------------------------------------------------------------------|
| New containers      | None (`provisioning-sim` already existed)                               |
| livekit-agents SDK  | No bump                                                                |
| provisioning-sim    | Dockerfile now installs shared packages (persistence, service-auth)    |

---

## What's New

### 1. Provisioning-sim: In-memory Ledger → PostgreSQL-backed Real Ledger

The previous `ProvisioningLedger` was an in-memory dict that reported success for operations that
never happened: it created a SIM record for any key it was given, kept no idempotency, and lost
everything on restart — so the agent could tell a caller "your SIM is unblocked" while the real
line stayed blocked. Every operation now mutates the real domain tables and is protected by the
database's own uniqueness on `idempotency_key`.

- **`provisioning.py` complete rewrite:**
  - Validates state transitions (unblock only `BLOCKED`, reactivate only `SUSPENDED`/`BLOCKED`,
    refuses `TERMINATED`).
  - Enforces idempotency via DB uniqueness — a replay returns the same reference, no second
    provisioning.
  - Resolves plan codes from `reference.products` catalog (matches product_code or display name,
    case-insensitively).
  - `ProvisioningError` surfaces business refusals honestly (404 for unknown customer/plan,
    409 for wrong state).
- **New endpoints:** `/sim/unblock`, `/sim/reactivate`, `/sim/roaming` (enable/disable toggle),
  `/subscription/{customer_id}` (read state).
- **Removed legacy:** `/sim/activate`, `/sim/deactivate`, `/sim/activate-roaming`.
- **`require_internal_key`** auth on all endpoints.
- **Sync `def` endpoints** (FastAPI threadpool) to avoid event-loop blocking on Postgres I/O.

### 2. Domain-core Ports Expansion

#### `CrmPort` — full CRM read surface

The port now covers everything the system reads from CRM today, so switching from the mock
(context-service Postgres) to a live CRM later is config, not redesign.

- **New dataclasses:**
  - `ContactInfo` — phone, email, preferred_language.
  - `SubscriptionLine` — subscription_id, msisdn, plan, status, roaming_enabled.
  - `Customer360` — full snapshot composed from client + contact + subscriptions.
- **`CrmUnavailable` exception** — distinct from "unknown customer" (404 → None). Without this
  split, the agent would tell a caller "I have no account for this number" during a CRM outage.
- **New abstract methods:** `get_contact()`, `get_subscriptions()`, `get_customer_360()`,
  `set_external_reference()`.

#### `ProvisioningPort` — rekeyed from MSISDN to customer_id

Keyed on `customer_id`, not on an MSISDN: every identifier that flows through the platform (policy
verdicts, execution ledger, audit) is the customer UUID, and the provisioning system is the
component that knows which line that customer holds.

- **Renamed/changed operations:**
  - `activate_sim(msisdn, iccid)` → `unblock_sim(customer_id)`
  - `deactivate_sim(msisdn)` → `reactivate_sim(customer_id)`
  - `replace_sim(msisdn, new_iccid)` → `replace_sim(customer_id, sim_type)`
  - `change_plan(msisdn, plan_code)` → `change_plan(customer_id, plan_code)`
  - `activate_roaming(msisdn)` → `set_roaming(customer_id, enable)`
- `unblock` and `reactivate` are separate (BLOCKED vs SUSPENDED start states).
- Every write carries an `IdempotencyKey`.

### 3. CRM Adapter (integration-adapters)

- **`LiveCrmAdapter`** completely rewritten:
  - `_get_or_raise()` / `_post_or_raise()` — distinguish 404 (None / []) from 5xx
    (`CrmUnavailable`). The agent never mistakes an outage for a customer-not-found.
  - Composed `get_customer_360()` with fallback: tries `/360` endpoint first, falls back to
    composing from client + contact + subscriptions (the object is the same either way).
  - `set_external_reference()` for write-back (e.g. `glpi_user_id`).
- **`MockCrmAdapter`** implements all new methods as no-ops.

### 4. Provisioning Adapter (integration-adapters)

- Rewritten to match the new `ProvisioningPort` contract: all operations keyed on `customer_id`,
  every write carries `idempotency_key`, roaming enable/disable via `set_roaming()`.

### 5. Executor (execution-service)

Updated dispatch to match the new provisioning adapter contract:
- `UNBLOCK_SIM` → `unblock_sim(customer_id, key)`
- `REACTIVATE_SIM` → `reactivate_sim(customer_id, key)`
- `ACTIVATE_ROAMING` → `set_roaming(customer_id, enable, key)`
- `REPLACE_SIM` → `replace_sim(customer_id, sim_type, key)` (was `new_iccid`)

### 6. NMS-sim + OCS-billing-sim

- Endpoint handlers changed from `async def` to `def` (sync threadpool) to avoid event-loop
  blocking on Postgres I/O.

### 7. Agent-worker Cleanup

- **Deleted `session/user_data.py`** — the old `SessionUserData` dataclass, replaced by
  `session_state.py` which is the live version.
- **`session_state.py`** — added `escalation_reason: str | None` field.
- **`sip_transfer.py`** — sets `user_data.escalation_reason` before offering a callback.
- **`clients/__init__.py`** — `routing_client` registered in `aclose_all_clients()`.

---

## Files Changed

| File | Change |
|------|--------|
| `services/provisioning-sim/src/provisioning_sim/provisioning.py` | In-memory → Postgres ledger (complete rewrite) |
| `services/provisioning-sim/src/provisioning_sim/main.py` | New endpoints + auth + sync handlers |
| `services/provisioning-sim/Dockerfile` | Installs shared packages |
| `services/provisioning-sim/pyproject.toml` | Depends on service-auth + persistence |
| `packages/domain-core/src/domain_core/ports/crm.py` | Expanded CrmPort + new dataclasses |
| `packages/domain-core/src/domain_core/ports/provisioning.py` | Rekeyed to customer_id |
| `packages/integration-adapters/src/integration_adapters/crm_adapter.py` | Live adapter rewrite |
| `packages/integration-adapters/src/integration_adapters/provisioning_adapter.py` | New contract |
| `services/execution-service/src/execution_service/executor.py` | Updated dispatch |
| `services/nms-sim/src/nms_sim/main.py` | async def → def |
| `services/ocs-billing-sim/src/ocs_billing_sim/main.py` | async def → def |
| `apps/agent-worker/src/session/user_data.py` | **Deleted** (replaced by session_state.py) |
| `apps/agent-worker/src/session/session_state.py` | Added escalation_reason |
| `apps/agent-worker/src/telephony/sip_transfer.py` | Sets escalation_reason |
| `apps/agent-worker/src/clients/__init__.py` | routing_client in aclose_all_clients |
| `apps/agent-worker/src/clients/routing_client.py` | Trivial whitespace fix |
| `packages/domain-core/src/domain_core/ports/__init__.py` | Export new symbols |