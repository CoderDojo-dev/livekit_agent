# Version 35 — Live-State Projections + Outstanding-Aware Billing

## Summary

This version makes every domain projection **write back to the live state** that
the Context façade reads, so an action's effect is immediately visible to the
agent. Previously, projections only recorded a receipt row (payment, recharge,
plan change) without updating the invoice/balance/subscription rows the agent
queries — so the caller would pay their bill and the very next question would
still answer "you owe 42.500 TND". Billing tools now distinguish the *invoice
total* from the *outstanding amount* (what is still owed after partial payments).

## Changes

### 1. Outstanding-Aware Billing (`apps/agent-worker/src/agents/`, `apps/agent-worker/src/tools/`)

**`billing_agent.py` — `request_payment_deferral`:**
- Unpaid amount calculation now reads `inv.get("outstanding", inv["amount"])` instead of `inv["amount"]`. This prevents overstating debt against the policy cap after a partial payment has been applied.

**`billing_tools.py` — `get_invoice_summary`:**
- Returns both `amount_due` (the outstanding balance) and `invoice_total` (the original frozen total).
- Message dynamically adapts: "fully paid; nothing is due" vs "with X still due on Y".

**`billing_tools.py` — `get_balance_summary`:**
- Postpaid "balance" now aggregates the **outstanding amount** across all open invoices, not just the latest invoice's frozen total.
- Message dynamically adapts: "account is settled" vs "you currently owe X".

### 2. Deterministic Invoice Ordering + Outstanding Field (`services/context-service/`)

**`repositories.py`:**
- Invoice query now `ORDER BY issue_date DESC` so the agent always sees the most recent invoice first (was non-deterministic heap order).

**`schemas.py`:**
- `Invoice` model now includes `outstanding: float = 0.0` — what is still owed after payments applied, separate from the frozen `amount`.

### 3. Live-State Execution-Service Projections (`services/execution-service/src/execution_service/projections.py`)

**Major refactor**: every projection now applies its effect to the **live database rows** the Context reads back, not just to an audit receipt. All live-state reads use `SELECT ... FOR UPDATE` for concurrent safety across actions on the same customer.

**`_payment()` — EXECUTE_PAYMENT:**
- Applies the payment amount FIFO against the outstanding balance of open invoices (oldest due first).
- Reduces `invoice.outstanding_amount` and sets status to `paid`/`partial`.
- Unapplied remainder (overpayment) is logged as credit.

**`_payment_plan()` — PAYMENT_DEFERRAL:**
- Pushes `invoice.due_date` forward by `requested_days`.
- Clears the `overdue` status on deferred invoices (back to `issued`).
- Uses `_target_invoices()` helper to target the named invoice or all open ones.

**`_recharge()` — TOP_UP:**
- Credits `BalanceAccount.balance_value` (the live prepaid main balance).
- Auto-creates a `BalanceAccount` row for the subscription if one doesn't exist yet.

**`_sim_case()` — UNBLOCK_SIM / REACTIVATE_SIM:**
- Restores `subscription.status = "ACTIVE"` so Customer-360 stops reporting the line as blocked.

**`_sim_order()` — REPLACE_SIM (NEW projection):**
- Writes a `SimOrder` row carrying the adapter reference as `tracking_code`.

**`_provisioning()` — CHANGE_PLAN / ACTIVATE_ROAMING:**
- CHANGE_PLAN: writes `PlanChangeHistory` reading `from_plan` from the **subscription row** (live state) instead of the fragile payload field; updates `subscription.plan_code`.
- ACTIVATE_ROAMING: sets `subscription.roaming_enabled = True`.

**New helpers:**
- `money(value)` — safe Decimal coercion for JSON amounts.
- `settle(amount, outstanding_invoices)` — FIFO payment allocation across invoices.
- `_dec(value)` — read a Numeric column as Decimal.
- `_subscription_id()` — resolve subscription from request or customer's active line.
- `_target_invoices()` — open invoices (or specific invoice) to apply payment/deferral to.
- `_main_balance()` — find or create the subscription's main prepaid balance.

### Files Changed

| File | Insertions | Deletions |
|------|-----------|-----------|
| `apps/agent-worker/src/agents/billing_agent.py` | 7 | 1 |
| `apps/agent-worker/src/tools/billing_tools.py` | 19 | 8 |
| `services/context-service/src/context_service/repositories.py` | 8 | 2 |
| `services/context-service/src/context_service/schemas.py` | 3 | 1 |
| `services/execution-service/src/execution_service/projections.py` | 208 | 21 |
| **Total** | **245** | **33** |

## Containers & Dependencies

- **No container image changes** in this version.
- **No SDK version bumps** (no livekit-agents, no framework upgrades).
- The new projections reference the following **persistence models** that must exist in the database:
  - `billing.Invoice.outstanding_amount` column (Numeric(12,2))
  - `ocs.BalanceAccount` table (prepaid main balance)
  - `crm.Subscription` table (for plan_code, roaming_enabled, status)
  - `provisioning.SimOrder` table (for REPLACE_SIM tracking)
- If these tables/columns aren't present, run the latest Alembic migrations before deploying.

## Testing Notes

- **Billing tools**: verify `get_invoice_summary` returns correct `amount_due` vs `invoice_total` after a partial payment. Verify `get_balance_summary` aggregates across all open invoices.
- **Payment projection**: execute a payment and confirm `invoice.outstanding_amount` decreases and status flips to `paid`/`partial`. Verify FIFO allocation across multiple open invoices.
- **Deferral projection**: execute a deferral and confirm `invoice.due_date` extends and `overdue` status clears.
- **Top-up projection**: execute a recharge and confirm `BalanceAccount.balance_value` increases by the recharge amount.
- **SIM projections**: execute UNBLOCK/REACTIVATE and confirm `subscription.status` becomes `ACTIVE`. Confirm `SimOrder` row created for REPLACE_SIM.
- **Provisioning**: execute CHANGE_PLAN and confirm `subscription.plan_code` updates and `PlanChangeHistory.from_plan` matches the prior plan code. Execute ACTIVATE_ROAMING and confirm `subscription.roaming_enabled = True`.
