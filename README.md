# Version 53 — Postgres-backed Provisioning Ledger, CRM Port Expansion & Adapter Rewrites

This branch replaces the in-memory provisioning simulator with a **real PostgreSQL-backed ledger**,
expands the CRM port with a full 360-degree customer view, and rewrites both adapters to match.

## What's new in v53

### Provisioning-sim: In-memory → PostgreSQL
- Complete rewrite of `provisioning.py`: validates state transitions (unblock only BLOCKED, reactivate only SUSPENDED/BLOCKED, refuses TERMINATED)
- Enforces idempotency via DB uniqueness — a replay returns the same reference
- Resolves plan codes from `reference.products` catalog (case-insensitive)
- New endpoints: `/sim/unblock`, `/sim/reactivate`, `/sim/roaming` (enable/disable toggle)
- Removed legacy: `/sim/activate`, `/sim/deactivate`, `/sim/activate-roaming`
- Auth via `require_internal_key`, sync `def` endpoints (FastAPI threadpool)
- Dockerfile now installs shared packages (`persistence`, `service-auth`)

### Domain-core Ports
- **CrmPort** expanded: `ContactInfo`, `SubscriptionLine`, `Customer360` dataclasses; `CrmUnavailable` exception (distinct from "unknown customer"); new abstract methods: `get_contact()`, `get_subscriptions()`, `get_customer_360()`, `set_external_reference()`
- **ProvisioningPort** rekeyed from MSISDN → `customer_id`: `unblock_sim()`, `reactivate_sim()`, `replace_sim(sim_type)`, `set_roaming(enable)`. Removed `activate_sim`/`deactivate_sim`/`activate_roaming`

### Adapter Rewrites
- **CRM adapter** (`LiveCrmAdapter`): `_get_or_raise()`/`_post_or_raise()` — 404 → None/[], 5xx → `CrmUnavailable` (agent never says "no account" during an outage). Composed `get_customer_360()` with fallback.
- **Provisioning adapter** (`LiveProvisioningAdapter`): all ops keyed on `customer_id`, idempotency key on every write

### Executor (execution-service)
- Updated dispatch: `UNBLOCK_SIM` → `unblock_sim()`, `REACTIVATE_SIM` → `reactivate_sim()`, `ACTIVATE_ROAMING` → `set_roaming()`, `REPLACE_SIM` takes `sim_type`

### Agent-worker Cleanup
- Deleted old `session/user_data.py` (replaced by `session_state.py`)
- Added `escalation_reason` field, `routing_client` in `aclose_all_clients()`

### NMS-sim + OCS-billing-sim
- Endpoint handlers: `async def` → `def` (sync threadpool) to avoid event-loop blocking on Postgres I/O

**Containers:** None new
**SDK:** No bump