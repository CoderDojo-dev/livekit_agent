# Version 66 — Policy Engine: Account-Action Rules, Idempotency Refinement, PII Guards

> **Base branch:** `version_65`
> **Files changed:** 20 modified, 1 new (+238 / -57)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |
| CONNECTOR_MODE     | Default changed `mock` → `live` (P6) |

---

## What's New

### 1. Account-Action Policy Rules (`services/policy-service/`)
**New file:** `rules/account.py` — Three deterministic rules for the three account-sensitive actions:

| Rule | Verdict | Logic |
|------|---------|-------|
| `check_top_up` | `TOP_OK` / `TOP_DENOMINATION` / `TOP_NO_AMOUNT` / `TOP_INVALID_AMOUNT` | Validates amount against configured `topup_denominations` (twelve-factor) |
| `check_change_plan` | `PLAN_OK` / `PLAN_NO_CODE` / `PLAN_UNKNOWN` / `PLAN_CATALOG_UNAVAILABLE` | Validates `plan_code` against `plan_codes` catalog |
| `check_roaming` | `ROAM_OK` / `ROAM_NO_DIRECTION` | Checks `enable` is present (`ACTIVATE_ROAMING` / `DEACTIVATE_ROAMING`) |

- `engine.py` registers the three new rules in `_ACTION_RULES`
- `config.py` adds `topup_denominations` and `plan_codes` with `field_validator` parsers for comma/semicolon-separated env values
- `schemas.py` adds `plan_code` and `enable` fields; `deferrals_this_year` changed from `int` to `int | None`

### 2. Policy Rule Refinements
- **Payment rule** (`rules/payment.py`): now validates that amount is present, positive, and does not exceed `unpaid_amount` before checking the hard cap. Amounts above the due are escalated for review.
- **Deferral rule** (`rules/deferral.py`): handles `deferrals_this_year=None` (history unavailable) by escalating instead of assuming 0.
- **Mandatory escalation** (`rules/mandatory_escalation.py`): `is_vip` is no longer escalated (P9). VIP customers pass through business rules like everyone else. The field remains in `PolicyContext` for audit.
- **Outbound guardrail** (`rules/outbound.py`): replaced generic 8-12 digit regex with typed PII patterns (customer ID, Tunisian mobile numbers, credit card groups). Only unmasked identifiers are caught.
- **Service layer** (`service.py`): new `_enrich()` method fills `deferrals_this_year` by counting succeeded `PAYMENT_DEFERRAL` actions from the action ledger (server-side, not client-trusted). Fails closed on DB error.

### 3. Idempotency Key Refinement (`apps/agent-worker/`)
- `session_state.py`: `new_idempotency_key()` now fingerprints the business payload (`action_type + sha256(payload)`) instead of just `action_type`. A fresh `release_idempotency_key()` drops the key after confirmed execution, so the next request is treated as a genuinely new action rather than a silent replay.
- `guarded_action.py`: contextual fields (`unpaid_amount`, `deferrals_this_year`) are excluded from the operation fingerprint so a retry with updated context is still recognized as the same operation. The key is released on any outcome indicating execution.

### 4. Execution Service Improvements (`services/execution-service/`)
- `executor.py`: mock references now carry a `MOCK-` prefix (`MOCK-PAY-...`, `MOCK-SIM-...`). Money-related actions (`EXECUTE_PAYMENT`, `TOP_UP`, `PAYMENT_DEFERRAL`) are refused in mock mode unless `ALLOW_MOCK_SENSITIVE=1`.
- `service.py`: domain projection failures now save the `error_message` on the `ActionLedger` row and log to the audit trail.

### 5. AccountServicesAgent Knowledge Upgrade (`apps/agent-worker/`)
- Added `build_knowledge_toolset()` and `knowledge_search` capability to AccountServicesAgent.
- Added read-only `get_balance_summary` / `get_invoice_summary` tools (payments/deferrals still route to billing).
- `_CORE` updated to include balance/invoice queries and the knowledge abstention rule.

### 6. BillingAgent Payload Fixes (`apps/agent-worker/`)
- `_outstanding_total()` extracted as a reusable helper.
- `make_payment` now sends `unpaid_amount` to policy for the new amount-vs-due check.
- `request_payment_deferral` no longer sends a fabricated `deferrals_this_year=0` (which disabled the `DEF_CAP` rule). Policy now counts it server-side from its own action ledger.

### 7. CONNECTOR_MODE Default Change (`packages/integration-adapters/`)
- Default changed from `mock` to `live` (P6: production safety). Tests explicitly set `CONNECTOR_MODE=mock`.

### Files Changed (20 modified, 1 new)

| Area | Files | Summary |
|------|-------|---------|
| `services/policy-service/` | `rules/account.py` **NEW**, `rules/payment.py`, `rules/deferral.py`, `rules/mandatory_escalation.py`, `rules/outbound.py`, `engine.py`, `config.py`, `schemas.py`, `service.py`, `tests/test_policy.py` | Account-action rules, payment amount-vs-due, deferral history escalation, VIP policy change, PII guard refinement, server-side enrich, config parsers |
| `services/execution-service/` | `executor.py`, `service.py`, `tests/test_executor.py` | MOCK prefix, sensitive-action guard in mock mode, projection-failure audit |
| `apps/agent-worker/` | `agents/account_services_agent.py`, `agents/billing_agent.py`, `session/session_state.py`, `tools/guarded_action.py`, `tests/test_persona_contract.py` | Knowledge + billing tools on AccountServices, idempotency fingerprint + release, contextual-field separation |
| `packages/integration-adapters/` | `config.py`, `tests/test_adapters.py` | CONNECTOR_MODE default → live |
| `scripts/` | `persona_contract_checks.py` | Exempt AccountServicesAgent from abstention-rule check |
