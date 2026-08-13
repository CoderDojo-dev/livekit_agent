# Version 88 — P2-2 dashboard truth completion (real failure_reason, audited close + auth routes, loopback ports, secrets hardening)

> **Base branch:** `version_87` (`d8fbe74`)
> **Commits:** 1 (P2-2 lot — code + cookbook spec)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none
> **Migration:** none (head stays `0017_notification_failure_reason`)
> **Rebuild:** required — notification-service (failure_reason real) + business-api (audited routes)
> **Port binding:** all 14 app-tier host ports now `127.0.0.1:` (H-4)

---

## Containers & SDK

| Item                  | Change                                                        |
|-----------------------|---------------------------------------------------------------|
| New containers        | None                                                          |
| livekit-agents SDK    | `1.6.5` (unchanged — `livekit-plugins-gladia==1.6.3` is a declared dev dep) |
| livekit-server        | `v1.8.4` (unchanged)                                          |
| agent-worker image    | No rebuild (P2-2 touches no worker code)                      |
| notification-service  | **Rebuild required** (`_record`/`_persist` real `failure_reason` + loud persist failure) |
| business-api image    | **Rebuild required** (audited escalation-close + 4 audited auth routes) |
| alembic head          | `0017_notification_failure_reason` (unchanged)                |
| Host port binding     | **All 14 app-tier ports bound to `127.0.0.1:`** (I2/H-4)      |
| `INTERNAL_API_KEY`    | Rotated in `.env` (gitignored); `.env.example` empty (unchanged) |

---

## What's New in This Branch

### Bundle F — Real `failure_reason` into the DB (completes R8)

`services/notification-service/src/notification_service/service.py` (combined edit F+H, AF3 verbatim):
- both send paths thread the real reason (`reason=str(exc)` at the `ContactUnavailable` branch,
  `reason=f"{type(exc).__name__}: {exc}"` at the provider end);
- `_record` now takes `reason: str = ""` and the in-memory dict carries the real reason (was the
  bare status string);
- `_persist` writes `failure_reason=(reason[:200] or None) if status == "failed" else None` against
  the v87 column;
- `_record` returns early with a `logger.warning` when `DATABASE_URL` is unset, and wraps `_persist`
  in `logger.exception` so a silent persist failure is now **loud** (was a `logger.warning: notification
  log write skipped` — the R9 gap).

### Bundle H — Silent persistence loss made loud (R9)

As above: the unset-DB guard and the `logger.exception(ERROR + traceback)` replace the swallowed
`except Exception: logger.warning(...)`. The forced-FK-rejection proof produced the intended
`notification log write FAILED [...] status=failed customer=...` log with a full traceback.

### Bundle G — Audited escalation close + auth routes (R3)

- new `_audit_actor(principal)` helper returning only `subject/kind/role/account_id` (deliberately
  no `session_id`, no `national_id`/PII) — placed **inside** `PgAuditLedger.append`, so the actor
  block is inside `entry_hash` and therefore **tamper-evident**;
- `close_escalation` now receives the acting `CurrentPrincipal` and appends an `escalation_closed`
  event (`actor/escalation_id/requested_resolution/resolution/target/trigger`) within the same
  `session_scope()` block as the mutation (commit-on-exit with the ledger);
- the four auth routes (`auth_login`, `auth_signup`, `auth_change_password`, `auth_revoke_all`)
  each audit-append on the **injected `DbSession`** + an explicit `session.commit()`. This follows
  the user decision to override the cookbook's `session_scope()` literal (that form would bypass the
  rolled-back test fixture and break `test_auth_http.py`).
- **Failed logins are not audited** (rate-limit 429 + lockout already record rejected attempts;
  noted in the login docstring).

### Bundle I — Secrets hardening + loopback (R16/H-4)

- `INTERNAL_API_KEY` rotated to a `secrets.token_urlsafe(32)` value **in `.env` only**;
  `.env.example` is untouched (empty key is the correct shipped default — `require_internal_key`
  is a no-op when unset). J4.5 grep confirms `dev-key-123` survives only in frozen/versioned files
  (`docs/versions/*`, `features_to_apply/*`, `answers.md`, historical phase docs) — never in live
  config, source, README or compose.
- `infra/docker-compose/docker-compose.apps.yml`: all 14 app-tier host bindings
  (`8101..8108`, `8201`, `8109:8107`, `8110:8108`, `8111:8109`, `8202`, `8203`) now `127.0.0.1:`.
  Non-breaking: every cross-service call uses a compose service name (e.g.
  `BUSINESS_API_URL=http://business-api:8108`, nginx `upstream business { server business-api:8108; }`)
  and host tooling uses `localhost`. Infra ports (LiveKit 7880-7882, redis 6379, postgres 5432,
  qdrant 6333, minio, otel) left untouched. **Note:** `INTERNAL_API_KEY` rotation requires restarting
  the consumer containers so they read `.env` at creation (compose `config` pulls `.env` at container
  create, not at compose-parse).

---

## Validation

- `ruff check apps/business-api services/notification-service` → **All checks passed!**
- `mypy` on `main.py` + `service.py` → **Success: no issues found in 2 source files**
- `docker compose -f docker-compose.yml -f docker-compose.apps.yml config --quiet` → **VALID**
- Full chain `test_committed.ps1 -Ref version_88`: **197/197 PASS**
  (business-api 66, agent-worker 104, notification 10, policy 17)

### Live invariant checks (J2/J3)

| Check                                | pre  | post | verdict |
|--------------------------------------|------|------|---------|
| `failure_reason IS NOT NULL AND status <> 'failed'` | 0 | 0 | holds    |
| `with_reason` (`failure_reason IS NOT NULL`)         | 0 | 1  | strictly greater |
| `failure_reason = 'failed'` (literal)               | 0 | 0 | never the literal |
| `length(failure_reason)` on the new row             | — | 200 | truncated to column width |

Real persisted row (forced via Twilio RFC test number `+15005550001`):
`HTTPStatusError: Client error '400 Bad Request' for url 'https://api.twilio.com/...` — a **real
provider rejection**, not fabricated.

### Audit ledger

- `GET /api/v1/audit/verify` → `{"intact": true}` **before and after** the G3 close route (chain
  preserved — the actor block is inside `entry_hash`).
- `escalation_closed` live proof: seq 157 (`transferred`/`transferred`) + 158
  (`requested=resolved` but resolution stays `transferred`, idempotent); error matrix
  404/400/403 leaves **zero** new ledger rows (`max(seq)` unchanged at 158 for non-actor requests).
- G4 auth events seq 156–162 (login → signup → password_changed → revoke_all),
  `{"intact": true, "entries": 56}` after — **append-only and verified**.
- `policy_verdicts=5` (unchanged across all P-cycles).

### Regression

- `pytest apps/business-api` → 66 passed (unchanged from v87); `pytest apps/agent-worker` → 104 passed
  (unchanged; no worker code touched).
- `verify_p0_1.sh` 20/20 ; `verify_p0_2.sh` 9/9 (with the extended `docs/versions/version_84.md`
  exclusion added in this patch).
- `make health` → 10/11 OK; only `knowledge-service:8102` DOWN = **pre-existing H-6** (torch hash
  mismatch), unrelated to P2-2.

### Cleanup

- Escalation close live proof rows restored via targeted
  `UPDATE conversation.escalation_cases SET resolution = NULL WHERE id = 'e07844e4-...'`
  (never `TRUNCATE`/`DROP`); ledger audit entries left in place (chain-safe). End state:
  58 open / 0 closed, `audit_ledger` back to its pre-P2-2 growth after the close was restored
  (the close route's own appends remain — honest record of the proof).

---

## Out of scope (unchanged)

- R11 / Bundle D (`customer_360` `!= "paid"` blacklist) — closed by user decision, `customer_360`
  byte-identical.
- R13 (`GET /api/v1/actions`) — no frontend caller.
- Root `tests/` not wired into CI (reported in v86).
- All items previously listed as out of scope in v79–v87.