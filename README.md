# Version 54 — Prepaid Recharge Denominations & Promotional Bonus Enforcement

This branch ensures prepaid recharges match the operator's actual product catalog: only fixed
denominations (5, 10, 20, 50 TND) are accepted, and the promotional bonus from the catalog
row is credited alongside the denomination.

## What's new in v54

### OCS billing-sim ledger
- **`_resolve_denomination()`** validates the top-up amount against `reference.recharge_catalog`:
  - Matches amount to a catalog row, returns `(amount, bonus, code)`
  - **Refuses unlisted amounts** with available denominations listed in the error message
  - Amounts rendered cleanly (5.00 → "5", 10.00 → "10") with bonus shown when present
- **`top_up()`** credits `amount + bonus` to the balance (was: arbitrary amount, no bonus)
- Empty catalog raises `LedgerError` rather than crediting silently

### Agent-worker `top_up` tool
- Docstring instructs the agent to:
  - Confirm a valid denomination (5, 10, 20, 50 TND) with the caller
  - Note that 10, 20, and 50 carry a promotional bonus
  - Refuse invented amounts and offer the catalog list on refusal

### Fixes applied
| Before | After |
|--------|-------|
| Any amount accepted; caller lost bonus | Only catalog denominations; bonus credited |
| Unlisted amount silently credited | Refused with available amounts listed |
| No bonus derived | Bonus picked from `reference.recharge_catalog` row |
| Empty catalog not handled | Raises `LedgerError` |

**Containers:** None
**SDK:** No bump