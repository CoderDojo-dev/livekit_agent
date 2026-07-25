# Version 54 — Prepaid Recharge Denominations & Promotional Bonus Enforcement

> **Base branch:** `version_53`
> **Commit range:** version_53..version_54
> **Files changed:** 2 (+63 / -5)

---

## Containers & SDK

| Item                | Change |
|---------------------|--------|
| New containers      | None   |
| livekit-agents SDK  | No bump|

---

## What's New

### Prepaid Recharge Catalog Enforcement

Prepaid recharges are sold in fixed denominations (5, 10, 20, 50 TND), and each denomination
carries a promotional bonus the customer is entitled to. Before this fix, `top_up()` accepted any
arbitrary amount and credited it without a bonus — the caller silently lost the promotional
credit they were promised, and unlisted amounts were treated as valid products the operator
doesn't sell.

#### OCS billing-sim ledger

- **New `_resolve_denomination()`** — validates the top-up amount against
  `reference.recharge_catalog`:
  - Matches the amount to a catalog row.
  - Returns `(amount, bonus, code)` tuple.
  - Unlisted amounts are refused with the available denominations listed in the error message
    (so the agent can read them to the caller).
  - Amounts rendered cleanly (5.00 → "5", 10.00 → "10") in the refusal message.
  - Bonus shown when present (e.g. `10 (+5 bonus)`).
- **`top_up()` updated** — the recharge row records what the customer paid; the balance
  increases by amount + bonus. The catalog is the operator's product list, not decoration.
- **Empty catalog** raises `LedgerError` rather than crediting silently.

#### Agent-worker `top_up` tool

- **Docstring updated** — instructs the agent to:
  - Confirm a valid denomination (5, 10, 20, 50 TND) with the caller before calling.
  - Note that 10, 20, and 50 TND carry a promotional bonus.
  - Refuse invented amounts.
  - Offer the catalog list on refusal (the error message lists them).

---

## Fixes Applied

| Before | After |
|--------|-------|
| Any amount accepted; caller lost bonus | Only catalog denominations; bonus credited with recharge |
| Unlisted amount silently credited | Refused with available amounts listed |
| No bonus derived | Bonus picked from `reference.recharge_catalog` row |
| Empty catalog not handled | Raises `LedgerError` |

---

## Files Changed

| File | Change |
|------|--------|
| `services/ocs-billing-sim/src/ocs_billing_sim/ledger.py` | `_resolve_denomination()` + `top_up()` rewrite (+57/-5) |
| `apps/agent-worker/src/tools/account_tools.py` | `top_up` docstring: denomination instructions (+11/-1) |