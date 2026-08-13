# Version 87 — P2-1 portal real identity + the four remaining dashboard truth gaps

> **Base branch:** `version_86` (`84956f1`)
> **Commits:** 1 (P2-1 lot — code + migration + cookbook spec)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** `0017_notification_failure_reason` (applied, head confirmed)
> **Rebuild:** required — business-api (auth routes + close_escalation + notification row change)

---

## Containers & SDK

| Item               | Change                                              |
|--------------------|-----------------------------------------------------|
| New containers     | None                                                |
| livekit-agents SDK | `1.6.5` (unchanged)                                 |
| livekit-server     | `v1.8.4` (unchanged)                                |
| agent-worker image | **Not rebuilt** — P2-1 touches no worker code        |
| business-api image | **Rebuild required** (main.py routes, repositories, billing) |
| alembic head       | `0017_notification_failure_reason` (on top of `0016`) |

---

## What's New in This Branch

### Bundle A — Portal real identity

The customer portal now authenticates against the same `auth.portal_*` identity layer P0-1 built,
and the signed-in profile reads **live CRM data** instead of invented fixtures.

- `repositories.py` → new `me_profile_detail(customer_id)`: returns `account_number` (first
  `billing.accounts`), `customer_since` (created_at iso), `plan` (subscription `plan_code`/`plan_type`),
  `msisidn` — **national_id is never selected** (the CIN is tokenised in `audit.pii_token_map`).
  Deliberately a separate method from `customer_360` (precedent: `customer_ledger`,
  `customer_service_actions`).
- `main.py` → `GET /api/v1/me/profile/detail`, cloning the sibling `/me/profile` idiom
  (`DbSession` + `ClientPrincipal`). `customer_id` comes from the principal, so no request
  identifier a caller could tamper with.
- Frontend customer portal:
  - `auth.server.ts` signup: `cin` → `cin_last4` (`cin.replace(/\D/g,"").slice(-4)`, `inputMode="numeric"`),
    `phone` → required `msisidn`.
  - `_portal/profile.tsx`: full real-identity rewrite (no invented data, locale via `Intl`
    fr-TN/ar-TN/en-GB, `Africa/Tunis` TZ, `reference` = `account_number`).
  - `customer.ts`: deleted only the `customer` fixture export (kept `sessions`/`securityEvents`/
    `notifications`).
  - `requests.ts`: removed `"...old Bramley Road flat number."` residue.
  - `portal-topbar.tsx`: wired to live `fetchProfileDetail` (initials from first+last, label = first
    name) — the cookbook A6 deletion had broken its `customer` import (cookbook named only the
    `notifications` accessor; the file also rendered the customer fixture).

### Bundle B — Escalation closure (R6)

- `repositories.py` → new `close_escalation(escalation_id, resolution)` (idempotent;
  `_ESCALATION_RESOLUTIONS = transferred, queued, callback_scheduled, resolved`; same serialised
  shape as `escalations()`).
- `main.py` → `POST /api/v1/escalations/{id}/close` (superviseur only).
- **Transaction fix:** the route uses `session_scope()` (commit-on-exit), not the sibling's
  read-only injected `DbSession` — the initial version returned 200 but failed to persist
  (Flushes but does not commit; `close_escalation` must own the transaction). Verified
  durable after rebuild.

### Bundle C — Notification failure reason (R8)

- `alembic/versions/0017_notification_failure_reason.py`: adds
  `billing.notifications.failure_reason String(200)` + check
  `failure_reason IS NULL OR status = 'failed'`. **Downgrade deviation:** the downgrade uses the
  raw constraint name `failure_reason_only_when_failed` (not `ck_notifications_...`) — alembic's
  `NAMING_CONVENTION["ck"]` double-prefixes; round-trip `head → downgrade 0016 → head` proven clean.
- `models/billing.py`: `Notification.failure_reason` + the `CheckConstraint`.
- `repositories.py`: `notification_list` row gains `"failure_reason"` beside `status`.
- `admin_dashboard`: `notifications.server.ts` row type gains `failure_reason: string | null`;
  `notifications.tsx` undermounts it in the status cell when `status === "failed"` and a reason
  exists.

### Bundle E — `system_overview` hardcoded status (R10)

- `repositories.py`: the 11 fake `{"status": "online"}` entries removed from the `services` list
  (Option 1, selected). `overview.tsx` never rendered them, so nothing breaks.

---

## Validation

- `ruff check .` → **All checks passed!**
- `mypy` on `repositories.py` / `main.py` / `billing.py` → **Success: no issues found in 3 source files**
- `bunx tsc --noEmit`: admin **exit 0**; customer portal **exit 0**
- Full chain `test_committed.ps1 -Ref version_87`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)
- `verify_p0_1.sh` 20/20 ; `verify_p0_2.sh` 9/9 (comment-filtered grep stays zero)
- Live round-trip B: `POST .../escalations/{id}/close` → 200, idempotent, **durable**
  (`still_open` drops by exactly N), closed rows 0→N; 403 client, 400 bogus resolution,
  404 unknown UUID
- Live C: `failure_reason` column live on the wire; `failure_reason` on a `sent` row
  violates the check constraint, `UPDATE` of a `failed` row succeeds (both test writes reverted)
- Live A: wrong-CIN + correct-CIN msisdn/signup → 401/200 exactly as the contract;
  `GET /api/v1/me/profile/detail` returns real CRM data (national_id never selected)
- Grep gates: `git grep "Amara|amara.osei|NX-4471|Bramley" -- Frontend/customer_portal/src` → 0
- Ledger append-only intact: `policy_verdicts=5`, `audit_ledger=47` (escalation close writes are
  idempotent and within the existing ledger row, never a schema mutation)

---

## Known issue (out of scope, not a v87 regression)

**`knowledge-service` DOWN** — pre-existing H-6. It was `Up 4 days (unhealthy)` and stuck at
"Waiting for application startup" *before* P2-1; the knowledge-service container was a **zombie**
on `make rebuild` (P2-1 had to `docker rm -f` it — removal, not kill). P2-1 does not touch that
service; `make health` is 10/11 OK with only knowledge-service down.

---

## Out of scope (unchanged)

- Root `tests/` not wired into CI (reported in v86).
- All items previously listed as out of scope in v79–v86.