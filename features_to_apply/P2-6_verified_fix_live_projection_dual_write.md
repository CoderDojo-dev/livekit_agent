# Cookbook — P2-6 Verified Fix: Live-Mode Projection Reconciliation (Dual-Write)

> **Base:** workspace HEAD after P2-4 + P2-5 (v91 era, alembic head
> `0017_notification_failure_reason`)
> **Scope:** ONE root cause, verified against source on 2026-08-16: in `CONNECTOR_MODE=live` the
> execution-service projections and the sims write the **same shared domain tables with the same
> idempotency key**. Depending on the action this produces either a unique-key collision (whole
> projection rolls back, audited `projection_failed`) or — worse — **silent double-apply** with no
> error anywhere.
> **Files changed:** 1 (`services/execution-service/src/execution_service/projections.py`) + tests.
> **Migration:** none. **Dependency change:** none. **New config:** none.
> **Containers to rebuild after apply:** `execution-service` only. Sims are NOT touched.

---

## 0. Verification verdict — CONFIRMED, and broader than the P2-5 report noted

The structural enabler (verified): the executor passes the **execution idempotency key through the
adapter to the sim** (`executor.py:68`, e.g. `:83-85`), and both sims write the shared `telecom`
database under that same key (`ocs-billing-sim/ledger.py:145`, `provisioning-sim/provisioning.py:119-124,
189-194`). Both sims state the invariant in their docstrings: *"protected by the database's own
uniqueness on idempotency_key."* The projections (`execution-service/projections.py`) were written
assuming they are the only writer. `dispatch()` (sim commit) completes **before**
`project_domain_effect()` runs (`service.py:74` → `:85-87`), so the sim's committed rows are always
visible to the projection's probes. Ordering is safe; the missing piece is that the projection
never looks.

### The full overlap matrix (every row traced to source)

| Action | Sim writes (live dispatch) | Projection writes | Live-mode outcome TODAY |
|---|---|---|---|
| `EXECUTE_PAYMENT` | `billing.payments` keyed row + oldest-invoice decrement (`ledger.py:207-241`) | `billing.payments` keyed row + FIFO settle of ALL open invoices (`projections.py:161-196`) | **Collision** on `payments.idempotency_key UNIQUE` (`models/billing.py:118`) → SAVEPOINT rollback → audited `projection_failed`; only the sim's oldest-invoice settlement stands |
| `PAYMENT_DEFERRAL` | zero-amount marker `payments` row keyed `DEFERRAL::<key>` + oldest invoice `due_date += days` (`ledger.py:244-271`) | `billing.payment_plans` row (no key) + **all open invoices** `due_date += days` (`projections.py:199-231`) | **No collision → SILENT double push**: the oldest invoice (the one the caller asked about) gets **+2·N days**; every other open invoice gets +N. Nothing is logged. |
| `TOP_UP` | `ocs.recharges` keyed row + balance `+= amount + bonus` (`ledger.py:115-153`) | `ocs.recharges` keyed row + balance `+= amount` (`projections.py:258-281`) | **Collision** on `recharges.idempotency_key UNIQUE` (`models/ocs.py:69`) → rollback; sim's credit (with bonus) stands |
| `UNBLOCK_SIM` / `REACTIVATE_SIM` | `sim.block_unblock_cases` keyed row + `status → ACTIVE` (`provisioning.py:71-101`) | same keyed row + same flip (`projections.py:284-303`) | **Collision** on `sim.py:33` UNIQUE → rollback; sim's effect stands |
| `REPLACE_SIM` | `sim.sim_orders` (TRK-…) + keyed `provisioning_requests` (`provisioning.py:104-126`) | a second `sim.sim_orders` (tracking = adapter reference), unkeyed (`projections.py:306-315`) | **No collision → SILENT double order**: two replacement SIMs shipped for one request, two tracking codes. Nothing is logged. |
| `CHANGE_PLAN` | `plan_change_history` + keyed `provisioning_requests` + `plan_code` (`provisioning.py:164-198`) | keyed `provisioning_requests` + `plan_change_history` + `plan_code` (`projections.py:318-346`) | **Collision** → rollback; sim's history row stands |
| `ACTIVATE_ROAMING` | keyed `provisioning_requests` + `roaming_enabled` (`provisioning.py:201-224`) | keyed `provisioning_requests` + `roaming_enabled` (`projections.py:318-348`, P2-4-fixed) | **Collision** → rollback (observed in the P2-5 live proof); sim's effect stands |

**Two distinct failure classes, one root cause:**
- **Class 1 — collisions (5 of 8 actions):** loud-ish (audited `projection_failed`, ledger stays
  `succeeded` by SAVEPOINT design). Subscriber state stays correct because the sim and the
  (P2-4-aligned) projection agree on values. But any projection-only effect dies in the rollback,
  and every live action sprays a false-alarm audit entry.
- **Class 2 — silent double-apply (`PAYMENT_DEFERRAL`, `REPLACE_SIM`):** no error, no audit
  anomaly, wrong real-world state. A deferral quietly grants double the days; a SIM replacement
  quietly ships two cards. This class is why "the ledger row is fine" is not a verdict.

**Why skipping projections in live mode is NOT the fix:** the projection is the platform's own
record ("Read and write must agree on one system of record", `projections.py:1-17`) — it alone
writes `billing.payment_plans`, and against a *real* external carrier system (which never touches
our DB) it is the only writer of everything. The correct general rule, already preached by the
sims themselves: **a transaction row carrying the execution idempotency key means the system of
record already applied the effect.** The projection just never checked.

---

## The fix — key-probe reconciliation in `projections.py` (one file)

One probing helper + one early-skip per projection function. **Mock mode is byte-identical**: no
keyed rows exist there, every probe returns False, every body runs exactly as today. Against a real
carrier system: same — no rows in our DB, projection writes everything, as designed. Against the
sims: the probe sees the sim's committed row and the projection becomes a precise no-op for the
effects already applied, while still writing platform-only records (the `PaymentPlan`).

### 1. Module docstring — append one paragraph (the "why", house style)

```python
"""Domain write projections (spec sections 5-7): the durable effect of an AUTHORIZED action.

... (existing paragraphs unchanged) ...

Live-mode reconciliation: the legacy system may write through these same tables under the SAME
idempotency key (the sims do; their ledgers are "protected by the database's own uniqueness on
idempotency_key"). A keyed transaction row therefore means the effect is already applied, and the
projection must not apply it a second time - colliding with the unique key rolls back the whole
SAVEPOINT, and re-applying an unkeyed effect (a due-date push, a SIM order) silently doubles it.
Each projection probes first; mock mode has no such rows and behaves exactly as before.
"""
```

### 2. Pure section — one offline-testable helper (next to `settle`, ~line 93)

```python
def deferral_probe_keys(key: str) -> tuple[str, str]:
    """The execution key plus the billing system's ``DEFERRAL::``-prefixed marker form of it.

    ocs-billing-sim records a deferral as a zero-amount payment marker row whose key is
    ``DEFERRAL::<execution key>`` (ledger.grant_deferral) so the key is consumed exactly once.
    Both forms mean "this deferral was applied by the billing system".
    """
    return key, f"DEFERRAL::{key}"
```

### 3. DB section — the probe (after `_dec`, ~line 117)

```python
def _effect_applied(session: Session, model, key: str | None) -> bool:
    """True when a transaction row already carries this execution key.

    The keyed tables (payments / recharges / block_unblock_cases / provisioning_requests) all carry
    ``idempotency_key ... unique=True``; one unique-index lookup per action, before any write.
    """
    if not key:
        return False
    return session.scalar(select(model).where(model.idempotency_key == key)) is not None
```

### 4. `_payment` (~line 161) — probe first, skip record + settlement

```python
def _payment(session: Session, req, ledger_row) -> None:
    if _effect_applied(session, Payment, req.idempotency_key):
        # Live mode: the billing system captured the payment and settled the invoice already.
        logger.info("payment %s already applied by the billing system; projection skipped",
                    req.idempotency_key)
        return

    account = _account_for(session, req.customer_id)
    # ... rest unchanged ...
```

### 5. `_payment_plan` (~line 199) — never push due dates twice, still record the plan

```python
    days = int(req.payload.get("requested_days") or 0)
    total = req.payload.get("amount") or req.payload.get("unpaid_amount") or 0
    count = req.payload.get("installment_count") or 1

    # Push the live due dates out; an overdue invoice that is now deferred is no longer overdue.
    deferral_until: date | None = None
    if _deferral_applied(session, req.idempotency_key):
        # Live mode: the billing system already pushed the due dates. Record the plan against the
        # CURRENT dates - pushing again would silently grant double the deferral.
        invoices = _target_invoices(session, req)
        deferral_until = max((inv.due_date for inv in invoices), default=None)
        logger.info("deferral %s already applied by the billing system; recording plan only",
                    req.idempotency_key)
    elif days > 0:
        for invoice in _target_invoices(session, req):          # unchanged from here
            new_due = invoice.due_date + timedelta(days=days)
            invoice.due_date = new_due
            if invoice.status == "overdue":
                invoice.status = "issued"
            if deferral_until is None or new_due > deferral_until:
                deferral_until = new_due
    else:
        logger.warning("deferral projection: non-positive requested_days for %s", req.customer_id)

    session.add(PaymentPlan(        # unchanged - the platform's own record is always written
        ...
    ))
```

with the probe helper placed next to `_effect_applied`:

```python
def _deferral_applied(session: Session, key: str | None) -> bool:
    """True when the billing system already applied this deferral (either key form)."""
    if not key:
        return False
    return session.scalar(
        select(Payment).where(Payment.idempotency_key.in_(deferral_probe_keys(key)))
    ) is not None
```

### 6. `_recharge` (~line 258) — probe first, skip record + credit

```python
def _recharge(session: Session, req, ledger_row) -> None:
    sid = _subscription_id(session, req)
    if sid is None:
        logger.warning("recharge projection skipped: no subscription on request")
        return
    if _effect_applied(session, Recharge, req.idempotency_key):
        # Live mode: the OCS credited the balance already - INCLUDING the catalog bonus, which
        # this projection does not add. Crediting again would double the money.
        logger.info("recharge %s already applied by the OCS; projection skipped",
                    req.idempotency_key)
        return
    # ... rest unchanged ...
```

### 7. `_sim_case` (~line 284) — probe first, skip record + status flip

```python
    action = sim_case_action(req.action_type)
    sid = _subscription_id(session, req)
    if action is None or sid is None:
        logger.warning("sim projection skipped: action=%s subscription=%s", action, req.subscription_id)
        return
    if _effect_applied(session, BlockUnblockCase, req.idempotency_key):
        logger.info("sim case %s already applied by the provisioning system; projection skipped",
                    req.idempotency_key)
        return
    # ... rest unchanged ...
```

### 8. `_sim_order` (~line 306) — the sim keys the REQUEST, not the order

```python
def _sim_order(session: Session, req, ledger_row) -> None:
    """REPLACE_SIM: raise a real replacement order carrying the dispatch reference."""
    # The provisioning system keys its provisioning_requests row, not the order; a keyed request
    # means the order was already placed. Without this probe, live mode ships two SIMs.
    if _effect_applied(session, ProvisioningRequest, req.idempotency_key):
        logger.info("SIM order %s already placed by the provisioning system; projection skipped",
                    req.idempotency_key)
        return
    sid = _subscription_id(session, req)
    # ... rest unchanged ...
```

### 9. `_provisioning` (~line 318) — one early-skip covers CHANGE_PLAN and ACTIVATE_ROAMING

```python
def _provisioning(session: Session, req, ledger_row) -> None:
    if _effect_applied(session, ProvisioningRequest, req.idempotency_key):
        # Live mode: the provisioning system recorded the request AND applied the effect
        # (plan_change_history + plan_code for CHANGE_PLAN; roaming_enabled for ACTIVATE_ROAMING).
        logger.info("provisioning %s already applied; projection skipped", req.idempotency_key)
        return

    sid = _subscription_id(session, req)
    # ... rest unchanged, including the P2-4 roaming line ...
```

### 10. Offline tests — extend `services/execution-service/tests/test_projections.py`

The file's contract is "pure mapping, no DB"; the new pure helper fits it exactly:

```python
from execution_service.projections import (
    deferral_probe_keys, installment_amount, projection_kind, sim_case_action,
)


def test_deferral_probe_keys() -> None:
    """Both key forms the billing system may have used for a deferral."""
    assert deferral_probe_keys("abc") == ("abc", "DEFERRAL::abc")
```

The DB-level behavior is integration-tested against the live stack (protocol below) — consistent
with the file's existing split (`test_executor.py` / `test_projections.py` are offline;
"DB writes are integration-tested", its line-1 docstring).

---

## Validation (run in this order)

1. **Static + offline suite**

   ```bash
   ruff check services/execution-service
   python scripts/run_tests.py
   ```

   Expected: ruff clean; all suites green, `services/execution-service` now including
   `test_deferral_probe_keys`. Mock-mode behavior is unchanged by construction (probes find no
   rows), so every existing execution-service test must pass unmodified — a failure here means the
   patch leaked a behavior change into mock mode; stop and re-read.

2. **Live-stack proof** — rebuild the single affected container:

   ```bash
   docker compose -f infra/docker-compose/docker-compose.yml \
                  -f infra/docker-compose/docker-compose.apps.yml up -d --build execution-service
   ```

   Then, against the seeded pilot customers (postpaid Amine `BA-000021` / prepaid Yousra),
   drive each live action through `ExecutionService.execute()` exactly as the P2-4/P2-5 proofs
   did, with a fresh verdict per run. For each, capture state **before** and **after**:

   | # | Action | Proof query | Pass criterion |
   |---|---|---|---|
   | 1 | `EXECUTE_PAYMENT` 5.000 | `SELECT count(*) FROM billing.payments WHERE idempotency_key='<key>'` | **1** (was: collision + `projection_failed`) |
   | 2 | `PAYMENT_DEFERRAL` 7 days | `SELECT due_date FROM billing.invoices WHERE invoice_number=<oldest>` before/after | moved **+7 days exactly** (was: +14); `billing.payment_plans` has 1 new row |
   | 3 | `TOP_UP` 5 (catalog denomination) | `SELECT balance_value FROM ocs.balance_accounts WHERE customer_id=… AND balance_type='main'` before/after | increased by **amount + bonus exactly once**; `ocs.recharges` has 1 row for the key |
   | 4 | `REPLACE_SIM` | `SELECT count(*) FROM sim.sim_orders WHERE subscription_id=… AND created_at > <run start>` | **1** (was: 2) |
   | 5 | `ACTIVATE_ROAMING` off→on | `crm.subscriptions.roaming_enabled` + `provisioning_requests` count for the key | follows payload; **1** request row; **no** new `projection_failed` audit entry |
   | 6 | `CHANGE_PLAN` | `SELECT count(*) FROM provisioning.plan_change_history WHERE subscription_id=… AND effective_date=CURRENT_DATE` | **1** per change |

   Global audit gate after all six:

   ```sql
   SELECT count(*) FROM audit.entries WHERE payload->>'action_type' IS NOT NULL
     AND event = 'projection_failed' AND created_at > now() - interval '15 minutes';
   -- expect: 0   (adjust column names to the audit schema in use)
   ```

3. **Mock-mode regression proof** — one mock `EXECUTE_PAYMENT` (P2-4 style): projection must still
   write the `payments` row and settle invoices (probes find nothing, bodies unchanged).

4. **Grep gates**

   | Gate | Expected |
   |---|---|
   | `grep -c "_effect_applied\|_deferral_applied" services/execution-service/src/execution_service/projections.py` | 2 defs + 6 call sites |
   | `grep -rn "DEFERRAL::" services/ packages/` | `ocs-billing-sim/ledger.py` (writer) + `projections.py` (probe) only |
   | `git diff --stat` | `projections.py` + `test_projections.py` only |

---

## Performance note (why this is the optimal shape)

Each probe is **one SELECT on a `UNIQUE` column** (`payments`/`recharges`/`block_unblock_cases`/
`provisioning_requests.idempotency_key` — all `unique=True`, hence indexed), issued once per action
on a path that already performs several writes. No N+1, no new round-trips beyond one indexed
lookup per execution. Net effect in live mode is *less* work than today: colliding projections no
longer pay for a doomed INSERT + SAVEPOINT rollback + audit write on every action.

## Regression risk assessment

| Change | Blast radius | Risk |
|---|---|---|
| Probes + early-skips in `projections.py` | All 8 guarded actions, live mode | Low. Mock mode byte-identical (no keyed rows → no behavior change; pinned by the unchanged existing suite). Live mode goes from "collision or double-apply" to "apply-once", which is the designed semantics. |
| `_payment_plan` records `deferral_until` from current dates when pre-applied | Portal/admin deferral views | Low: the value now reflects the actual post-push state instead of a recomputation — more truthful, not less. |
| Accepted semantics divergence | Live `EXECUTE_PAYMENT` settles oldest-invoice-first (sim), mock settles all-open FIFO (projection) | Accepted and documented: the billing system of record owns allocation when it wrote the keyed row. Pre-existing sim behavior, not introduced here. |

## Explicit non-goals (do not "improve" while applying)

- **Sims untouched.** The alternative design — changing `grant_deferral`'s marker from
  `DEFERRAL::<key>` to the plain key so one probe form covers everything — is cleaner in the
  abstract but touches a second service, changes the sim's marker contract, and buys nothing
  behavioral. The two-form probe keeps P2-6 single-service. If a future cleanup wants the uniform
  key, it is a one-line sim change plus deleting one tuple element here.
- No `ON CONFLICT DO NOTHING` / schema changes — probing matches the file's existing
  select-then-insert idiom (same pattern as `ticketing_glpi/adapters/mirror.py:71-72`).
- No mock-mode bonus alignment (projection credits `amount`, sim credits `amount + bonus`) —
  pre-existing mock-fidelity gap, invisible now that live mode defers to the sim. Logged here as
  an observation only.
- No change to `service.py`'s SAVEPOINT wrapper — it stays as the last-resort guard; after this
  patch it should simply never fire for dual-write reasons.
- No `is_live()` branches in projections — the probe is mode-agnostic by design, so the code
  cannot drift between modes.
