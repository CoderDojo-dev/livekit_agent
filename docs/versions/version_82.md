# Version 82 — Callback lifecycle, customer ledger, service actions, notification log, outstanding amount + truth-in-labelling corrections

> **Base branch:** `version_81` (`2f10a07`)
> **Commits:** 1 (features lot)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none

---

## Containers & SDK

| Item               | Change                          |
|--------------------|---------------------------------|
| New containers     | None                            |
| livekit-agents SDK | `1.6.5` (unchanged)             |
| livekit-server     | `v1.8.4` (unchanged)            |
| Docker Compose     | Unchanged                       |
| Business-api       | **No image rebuild required** — additive read routes; reload on deploy |
| Agent-worker image | No rebuild required (no agent-worker change) |

---

## What's New in This Branch

Six cookbooks applied on top of `version_81` (all read-only except UI rendering; backend is
additive `repositories.py`/`main.py` — no existing key removed or renamed).

### FEATURE_15 — Callback lifecycle evidence (`/callbacks`, pure frontend)

Decision D11 re-verified: `callbacks.py to_dict()` already serialised `attempts`,
`outcome_note`, `completed_at`, `assigned_advisor_id`, `assigned_advisor_name`,
`session_id` — the gap was **render-only**. New read-only detail modal
`callback-lifecycle.tsx` surfaces them; the action cell opens it. `MASTER_APPLY_RUNBOOK`
records the correction (the model-comment "promise nobody can prove was kept" was already
on the wire).

### FEATURE_16 — Customer ledger (`GET /api/v1/customers/{id}/ledger`)

New `SupervisionRepository.customer_ledger()`: latest **50** payments, payment plans and
consent captures per customer, batched invoice-number lookup, hard-capped, `None` → 404.
Deliberately a **separate method** so `customer_360`'s return shape is untouched for
existing callers. Consumed by the new ledger modal in `customer-detail.tsx`.

### FEATURE_17 — Service actions (`GET /api/v1/customers/{id}/service-actions`)

New `customer_service_actions()`: live balances + plan changes + a merged chronological
**events stream** (recharges, SIM cases/orders, provisioning requests) scoped through the
customer's live subscriptions — required because `sim.block_unblock_cases` and
`provisioning.plan_change_history` carry no `customer_id` while two other tables allow
NULL. Merged stream sorted by UTC `occurred_at`, capped at 50.

### FEATURE_18 — Notification send log (`GET /api/v1/notifications`)

New `notification_list()` (billing.notifications, newest first, `channel`/`status` filters,
per-status `counts`, clamp 1..200, batched customer hydration). **Read-only**: never sends,
never retries a failed send. `customer_id` is nullable by design (advisor pages are
unattributed, not missing). New `/notifications` route + nav entry + query key + page with
channel/status filters and load-more. Contract tests assert shape + clamping (`limit=0`→1,
`offset=-5`→0) — never seeded content.

### FEATURE_20 — Truth-in-labelling corrections

- **C-1**: `customer-view.ts`/`customer-detail.tsx` — honest unpaid-total footer
  (`OWED_STATUSES` guard + `unpaidTotal`) replaces the misleading "Total invoiced".
- **C-2**: "Attributed turns" → **"Caller turns"** (`agents.tsx`, `agent-detail.tsx`) — the
  metric counts caller turns, not persona-attributed work. C12 backlog.
- **C-3**: `POLICY_*` co-location documented (D13 runbook debt).
- Corrections are bundled per the tree's `RUNBOOK_V2_CORRECTIONS` precedent.

### FEATURE_21 — `Invoice.outstanding_amount`

`customer_360` open-invoices adds one additive **`outstanding`** key (both columns NOT NULL
with server_default 0 → no guard needed), consumed by the C-1 unpaid-total footer. The
§6-B follow-up FEATURE_20 flagged; FEATURE_19 (notification failure-reason, needs a column +
Alembic migration in locked `packages/persistence`) stays parked by design.

---

## Validation

- business-api suite: **28/28 PASS** (24 pre-existing + 4 new: ledger/service-actions
  unknown-customer → None, notification shape + clamping)
- Full chain `test_committed.ps1 -Ref version_82`: **140/140 PASS**
  (business-api 28, agent-worker 85, notification 10, policy 17)
- `bunx tsc --noEmit` on `Frontend/admin_dashboard` → **CLEAN** (exit 0)
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47`
- No migration, no env change, no dependency change

---

## Out of scope (unchanged)

- FEATURE_19 (notification failure-reason capture) — needs new column + Alembic migration in
  `packages/persistence`; parked and unbuilt.
- All items previously listed as out of scope in v79/v80/v81.