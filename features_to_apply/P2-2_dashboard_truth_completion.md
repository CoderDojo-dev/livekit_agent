# P2-2 — Implementation Cookbook

**Base:** `version_87`, code commit `31c38cf`, HEAD `d8fbe74` (docs-only, +117 on
`docs/versions/version_87.md`). Every verbatim block below is current at both.

**Bundles:** F (notification failure reason, completes R8) · G (audit actor + audit the close
route, R3) · H (R9 silent persistence failure) · I (secrets hardening, R16 / H-4).

**No tests, no CI, no test libraries.** Verification is live and manual, expressed as invariants.

---

## §0 — Read this before you open an editor

### Conventions in force (violating these is what broke the last two patches)

1. **Clone-the-sibling applies to reads only. Every mutation route owns its transaction via
   `session_scope()`.** P2-1's close route returned HTTP 200 with an unchanged database because it
   cloned a read sibling's injected `DbSession`, which never commits.
2. **`PgAuditLedger.append` is flush-only — the caller owns the commit.** An append must sit inside
   the same `session_scope()` block as the mutation it describes, or the two will not land together.
3. **Never hand-format imports.** Add the line, then run `python -m ruff check --fix <path>`.
4. **Alembic re-applies `NAMING_CONVENTION` on drop.** Pass constraint names **raw** to
   `op.drop_constraint`, never pre-prefixed. (No migration in P2-2, but the rule stands.)
5. **Do not claim what a component renders without opening it.** A file size from a directory
   listing is not a read.
6. **Express every expectation as an invariant or a query, never a literal count.**
7. **Never insert `audit.audit_ledger` rows from raw SQL.** Go through `PgAuditLedger`.

### Bundles F and H edit the same two methods

`NotificationService._record` and `NotificationService._persist` are touched by **both** F (thread
the real reason through) and H (make the silent swallow loud). Applying them as two separate edits
will conflict. **§F3 gives one combined final form of both methods — apply that once.**

### Deliberately not in scope

- **R11 / Bundle D** — `customer_360`'s `!= "paid"` blacklist. Closed by your decision; `customer_360`
  stays byte-identical.
- **R13** — `GET /api/v1/actions` has no frontend callers.
- **Propagating notification persistence failures.** Bundle H makes the failure loud, not fatal. See
  §H2 for why that boundary is deliberate.

---

# BUNDLE F — Notification failure reason (completes R8)

`0017` shipped `billing.notifications.failure_reason varchar(200) NULL` with CHECK
`ck_notifications_failure_reason_only_when_failed` (`failure_reason IS NULL OR status = 'failed'`).
The column has exactly one writer and that writer never sets it, so `with_reason = 0` is structural.

The cause is already computed. `notify()` produces a real reason in all three failure branches and
returns it over HTTP, then discards it at the `_record` boundary. Bundle F stops discarding it.

All edits are in **`services/notification-service/src/notification_service/service.py`**.

## F1 — module docstring

Replace:

```python
sent=False is returned with the actual reason. The DB record is written with status='failed'.
```

with:

```python
sent=False is returned with the actual reason. The DB record is written with status='failed'
and that same reason in failure_reason (truncated to the column width).
```

## F2 — the two `_record` call sites

**Contact-resolution branch** — replace:

```python
                self._record(req, status="failed", reference="")
```

with:

```python
                self._record(req, status="failed", reference="", reason=str(exc))
```

**End of `notify()`** — replace:

```python
        self._record(req, status=status, reference=reference)
```

with:

```python
        self._record(req, status=status, reference=reference, reason=reason)
```

By that line `reason` is already bound in every path: `""` on success, `str(exc)` for
`ChannelUnavailable`, `f"{type(exc).__name__}: {exc}"` for a bare `Exception`.

## F3 — `_record` and `_persist`, combined final form (Bundle F + Bundle H)

Replace both methods in full with:

```python
    def _record(self, req: NotifyRequest, status: str, reference: str,
                reason: str = "") -> None:
        self._sent.append({
            "customer_id": req.customer_id, "channel": req.channel,
            "template": req.template, "reference": reference,
            "sent": status == "sent", "reason": "" if status == "sent" else reason,
        })
        if not os.getenv("DATABASE_URL"):
            logger.warning(
                "notification NOT persisted, DATABASE_URL unset [%s/%s] status=%s",
                req.channel, req.template, status,
            )
            return
        try:
            self._persist(req, status, reason)
        except Exception:
            logger.exception(
                "notification log write FAILED [%s/%s] status=%s customer=%s",
                req.channel, req.template, status, req.customer_id,
            )

    @staticmethod
    def _persist(req: NotifyRequest, status: str, reason: str = "") -> None:
        from persistence.engine import session_scope
        from persistence.models.billing import Notification
        from persistence.util import to_uuid

        with session_scope() as session:
            session.add(Notification(
                customer_id=to_uuid(req.customer_id),
                channel=req.channel,
                template_code=req.template,
                status=status,
                failure_reason=(reason[:200] or None) if status == "failed" else None,
            ))
```

Three things changed beyond adding the parameter:

- `"reason"` in the in-memory `_sent` record was `"" if status == "sent" else status`, which stored
  the literal string `"failed"`. It now stores the real cause.
- `failure_reason` is `None` unless `status == "failed"`, which is what the CHECK requires. An empty
  reason collapses to `None` via `or None` rather than storing `""`.
- `reason[:200]` matches the column width. A provider traceback string will exceed it.

The `if os.getenv(...)` block became an early return so the unset-`DATABASE_URL` path can log. Same
outcomes, one new log line — that half is Bundle H.

---

# BUNDLE G — Audit actor and the unaudited close route (R3)

`entry_hash = sha256(previous_hash | canonical(payload) | timestamp)`. The payload is **inside** the
hash, and `AuditLedgerEntry` has no actor column. So the actor goes in the payload: tamper-evident
for free, `verify_chain` untouched, **no migration**. A new column would sit outside the hash and
need a migration — strictly worse on both counts.

P2-1 made `POST /api/v1/escalations/{escalation_id}/close` the first staff-mutating endpoint in the
system, and it writes no ledger entry.

All edits are in **`apps/business-api/src/business_api/main.py`**.

## G1 — imports

`main.py` already has both of these (lines 16 and 32) — confirm, do not duplicate:

```python
from audit_trail import PgAuditLedger
from persistence import get_session, session_scope
```

Add, if absent:

```python
from persistence.util import to_uuid
```

`closed["session_id"]` is a `str` (`repositories.close_escalation` returns `str(case.session_id)`)
and `AuditLedgerEntry.session_id` is `UUID(as_uuid=True)`, so the conversion is required.

> Adaptation check: do not hand-place that import. Add the line anywhere in the import block, then
> run `python -m ruff check --fix apps/business-api`. Ruff treats `persistence` as first-party and
> will sort it correctly; hand-placing it is how I produced two I001 failures in earlier patches.

## G2 — actor helper

Add immediately above the `EscalationClosePayload` class:

```python
def _audit_actor(principal: Principal) -> dict:
    """Actor block for audit payloads. Inside the hash, so it is tamper-evident.

    Deliberately omits principal.session_id: that is the auth-session identifier and the ledger is
    append-only and immutable. Never include national_id or any other PII.
    """
    return {
        "subject": principal.subject,
        "kind": principal.kind,
        "role": principal.role,
        "account_id": str(principal.account_id) if principal.account_id else None,
    }
```

> Adaptation check: `Principal` must be importable in `main.py` for that annotation. The existing
> `CurrentPrincipal` alias is `Annotated[Principal, Depends(current_principal)]`, so it is almost
> certainly already imported — confirm before adding anything.

## G3 — the close route

Replace the route body in full. **Left column is the shipped v87 text; apply the right.**

```python
@app.post("/api/v1/escalations/{escalation_id}/close")
def close_escalation(
    escalation_id: str,
    payload: EscalationClosePayload,
    role: SuperviseurRole,
    principal: CurrentPrincipal,
) -> dict:
    """Set the outcome on an open handoff (idempotent). Audited with the acting principal."""
    with session_scope() as session:
        try:
            closed = SupervisionRepository(session).close_escalation(
                escalation_id, payload.resolution
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if closed:
            PgAuditLedger(session).append(
                to_uuid(closed["session_id"]), "escalation_closed",
                {
                    "actor": _audit_actor(principal),
                    "escalation_id": closed["id"],
                    "requested_resolution": payload.resolution,
                    "resolution": closed["resolution"],
                    "target": closed["target"],
                    "trigger": closed["trigger"],
                },
                entity_reference=f"escalation_cases:{closed['id']}",
            )
    if not closed:
        raise HTTPException(status_code=404, detail="escalation not found")
    return closed
```

Four deliberate properties:

- **The append is inside the `with`.** `PgAuditLedger.append` only flushes, so the escalation write
  and its ledger entry commit as one transaction. Moving it outside means the audit entry is silently
  discarded — the same class of bug as P2-1's `DbSession` mistake.
- **`if closed:` guards it.** A 404 writes no entry and commits an empty transaction. A 400 raises
  inside the block and rolls back.
- **`requested_resolution` alongside `resolution`.** `close_escalation` is idempotent: a case that
  already carries an outcome is returned unchanged. When those two fields differ, the ledger records
  a rejected overwrite attempt. This needs **no change to `close_escalation`**, which stays exactly
  as P2-1 shipped it. Known limitation: closing twice with the *same* resolution produces two
  similar entries, distinguishable only by `seq` and `created_at`. That is acceptable — the ledger
  records attempts, and the escalation state is unambiguous.
- **`session_id` is the call session, not the auth session.** `EscalationCase.session_id` is NOT
  NULL, and the ledger's `session_id` column is indexed, so every entry is queryable per call.

`"escalation_closed"` is 17 characters against `event_type String(40)`, and joins the existing
`"consent"` and `"data_retention"` vocabulary. `SupervisionRepository.audit_entries(limit,
before_seq, event_type)` already filters on `event_type`, so this is queryable from the dashboard
the moment it lands — no reader change.

## G4 — the four unaudited auth mutations (follow-on, needs a read first)

`POST /api/v1/auth/login`, `/auth/password`, `/auth/sessions/revoke-all` and `/auth/signup` mutate
security state and write no ledger entry. **I do not have those four route bodies verbatim, so I am
not writing their code here.** Open them, then apply the identical shape as G3 with:

| Route | `event_type` | `entity_reference` |
|---|---|---|
| `/auth/login` | `auth_login` | `portal_accounts:<account_id>` |
| `/auth/password` | `auth_password_changed` | `portal_accounts:<account_id>` |
| `/auth/sessions/revoke-all` | `auth_sessions_revoked` | `portal_accounts:<account_id>` |
| `/auth/signup` | `auth_signup` | `portal_accounts:<account_id>` |

Rules that carry over unchanged: payload gets `"actor": _audit_actor(principal)`; **never** put a
password, hash, token, or `national_id` in the payload — it is permanent and immutable; append
inside the same `session_scope()` as the credential write; `session_id` is `None` for auth events
(mirror `retention.py`, which passes `None`).

Failed logins are the interesting case: auditing them turns the ledger into a brute-force record,
but the login path is rate-limited and lockout-bearing already. Decide explicitly rather than by
accident, and if you audit failures, record only `{"subject": <submitted>, "outcome": "rejected"}`.

---

# BUNDLE H — R9: the silent persistence failure

**The code for this bundle is already in §F3.** Bundle H and Bundle F edit the same two methods, so
they are applied as one edit. This section records what H changed and, more importantly, what it
deliberately did not.

## H1 — what changed

Before, two independent failure modes were invisible:

```python
        if os.getenv("DATABASE_URL"):          # unset -> persistence skipped, no log at all
            try:
                self._persist(req, status)
            except Exception as exc:
                logger.warning("notification log write skipped: %s", exc)   # no traceback, WARNING
```

After (§F3): the unset-`DATABASE_URL` path emits a `logger.warning` naming the channel, template and
status that were dropped, and the exception path is `logger.exception` — **ERROR level with the full
traceback**, plus the channel, template, status and customer needed to reconstruct the lost row.

`"log write skipped"` was also actively misleading: a skip is a decision, and this was a failure.

## H2 — why the failure is loud but not fatal

Do **not** propagate. `notify()` is called on the live voice path; the notification-service is
invoked by the agent worker mid-call. Raising here would convert a database hiccup into a failed
customer notification and, upstream, a degraded call. The send already succeeded at that point — the
SMS or WhatsApp message is out the door — so failing the response would also make the HTTP result
lie in the opposite direction.

The correct boundary: the durable log is best-effort, the failure is loud and attributable, and the
send result stays truthful. That is what §F3 implements.

## H3 — the one thing intentionally left out

A process-level failure counter, or recording the exception on an `observability_kit` span, would
make this queryable rather than greppable. Both need a read I have not done: a counter needs
`NotificationService.__init__` verbatim (a `global` statement risks a lint rule I cannot confirm is
unselected), and a span needs `observability_kit`'s exception API — `ledger.py` only shows me
`trace_span("audit.append", ...)`, not whether it records exceptions. **Do not guess either.** If you
want it, read those two first; the `logger.exception` above is the complete fix for R9 on its own.

---

# BUNDLE I — Secrets hardening (R16 / H-4)

Two separate problems. The mechanism is already correct in both cases; the dev values are not.

## I1 — rotate `INTERNAL_API_KEY`

`.env` line 30 currently reads:

```
INTERNAL_API_KEY=dev-key-123            # unset = disabled (dev)
```

`.env.example` line 30 ships it **empty**, so staging and production already take a real secret. Only
the working `.env` carries the placeholder, and `packages/service-auth`
(`internal_headers()` / `require_internal_key`) enforces it across every internal hop.

Generate a real value — **`openssl` is not installed on this machine**, so use Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Replace the value in `.env`, keeping the comment:

```
INTERNAL_API_KEY=<the generated token>   # unset = disabled (dev)
```

**`.env` is untracked and stays untracked.** Do not touch `.env.example` — empty is the correct
shipped default, and putting a real token there would publish it.

`INTERNAL_API_KEY` is read by every service that calls another, so all of them must see the new
value simultaneously. Compose reads `.env` at container-create time, not build time, so an env-only
change needs `docker compose up -d` (recreate), **not** a rebuild. Bundles F and G force a rebuild
anyway — see §J1.

> Failure mode to watch: any service still holding the old key returns 401 on internal calls. §J3
> gives the invariant that catches it.

## I2 — stop publishing `:8108` to every interface

`infra/docker-compose/docker-compose.apps.yml` line 123 (business-api):

```yaml
    ports: ["8108:8108"]
```

That binds `0.0.0.0`, so the business API is reachable from anything that can route to this host —
bypassing the nginx gateway, and with it every header, TLS and rate-limit assumption the gateway
carries. Change to:

```yaml
    ports: ["127.0.0.1:8108:8108"]
```

This is non-breaking for the way the system is actually run: both dev servers reach the API over
loopback (`BUSINESS_API_URL` defaults to `http://localhost:8108`, admin on `:8081`, portal on
`:8080`), and container-to-container traffic never used the published port — it uses the compose
network.

> Adaptation check, and I mean it: confirm line 123 is the business-api service before editing, and
> confirm nothing off-box consumes `:8108` (a phone, a tablet, another dev machine on the LAN). If
> something does, that consumer belongs behind the gateway, and that is a larger change than this
> bundle.

**Line 158 (`["8110:8108"]`) maps a different service's container 8108 to host 8110. I have not read
that file, so I am not prescribing an edit to it.** The same loopback treatment applies to every
host-published application port that has no off-box consumer — open the file, list the `ports:`
entries, and decide each one deliberately. Leave the infrastructure ports (Postgres, LiveKit, the
gateway itself) alone unless you have a reason.

---

# §J — Apply order and verification

## J1 — order

1. **F + H together** — one edit to `service.py` (§F1, §F2, §F3).
2. **G** — `main.py` (§G1, §G2, §G3). G4 only after reading the four auth routes.
3. **I** — `.env` and `docker-compose.apps.yml`.
4. `python -m ruff check --fix apps/business-api services/notification-service`, then
   `python -m ruff check` on both — must be clean.
5. `mypy` on the two touched files.
6. Rebuild. Both changed services bake their source into the image, so a restart is not enough:
   `make rebuild`. If it stalls on the four-day-old `docker-compose-knowledge-service-1` zombie,
   `docker rm -f` it (removal works where kill does not), then `docker compose ... up -d --build`
   and `up -d` manually.
7. `make health` — expect one service down: `knowledge-service:8102`, which is H-6
   (`torch==2.2.2` hash mismatch) and pre-existing. Anything else down is yours.

**No migration.** `0017` already shipped the column; the actor lives in the existing JSONB payload.
Head stays `0017_notification_failure_reason`.

**No frontend changes.** `notifications.tsx` already undermounts `failure_reason` when
`status === "failed"` (P2-1 Bundle C), and `SupervisionRepository.audit_entries` already filters on
`event_type`, so the new ledger entries are visible through the existing audit surface. If either
renders nothing after this patch, the bug is in the backend, not the UI.

## J2 — Bundle F, live

Force a real failure rather than fabricating a row: send a notify request for a customer with no
reachable contact on the requested channel, which raises `ContactUnavailable`. Then assert on shape,
not on counts:

```sql
-- must be 0 both before and after: the CHECK and the writer agree
SELECT count(*) AS violations FROM billing.notifications
 WHERE failure_reason IS NOT NULL AND status <> 'failed';

-- must be strictly greater than it was before the patch (it was 0, structurally)
SELECT count(*) AS with_reason FROM billing.notifications WHERE failure_reason IS NOT NULL;

-- the reason must be the provider's text, never the literal 'failed'
SELECT status, failure_reason, created_at FROM billing.notifications
 WHERE status = 'failed' ORDER BY created_at DESC LIMIT 5;
```

The third query is the one that matters. `failure_reason = 'failed'` means §F3 was applied to
`_persist` but not to `_record`, and the old `else status` expression is still feeding it.

Do not assert `failed_rows = 33`. That number drifted from 28 between my inventory and P2-1 because
the writer keeps running; it will drift again.

## J3 — Bundle G, live

Pick an open escalation, close it as a supervisor, then:

```sql
-- newest entry is the close, and the actor is a real staff principal
SELECT event_type, entity_reference,
       payload->'actor'->>'subject' AS actor_subject,
       payload->'actor'->>'role'    AS actor_role,
       payload->>'requested_resolution' AS requested,
       payload->>'resolution'           AS resolution
  FROM audit.audit_ledger ORDER BY seq DESC LIMIT 3;
```

Invariants:

- `event_type = 'escalation_closed'`, `actor_role = 'superviseur'` or `'administrateur'`,
  `actor_subject` is the staff email — not null, not `'unknown'`.
- `requested = resolution` on a first close.
- `GET /api/v1/audit/verify` still reports the chain valid. **This is the decisive gate**: it proves
  the payload-in-hash approach did not break `verify_chain`, which is the entire justification for
  putting the actor in the payload instead of a new column.
- Close the *same* escalation again: still 200, `resolution` unchanged, and a second ledger entry
  appears with `requested` ≠ `resolution` if you send a different resolution — that is the recorded
  rejected-overwrite attempt.
- Idempotency of the *audit* is not claimed. A repeat close is a repeat event.
- Unknown UUID → 404 **and no new ledger row** (`select max(seq)` unchanged).
- `{"resolution":"bogus"}` → 400 **and no new ledger row**.
- Client token → 403, unchanged from P2-1.

Then the internal-key check from Bundle I, which shares this rebuild: exercise one internal hop that
goes through `require_internal_key` — an advisor lookup or a callback write from the worker. A 401
there means a service did not get the rotated key.

**Restoring state after testing:** reset the escalation with a targeted
`UPDATE conversation.escalation_cases SET resolution = NULL WHERE id = '<uuid>'` — never TRUNCATE,
never DROP (H-2). **The ledger entries cannot be cleaned up the same way.** The chain is hash-linked,
so deleting a middle entry permanently breaks `verify`. Deleting only the highest-`seq` entry is
chain-safe (`seq` is an Identity column, gaps are fine), but the honest choice is to leave them: a
supervisor really did close that escalation, and that is exactly what an append-only ledger is for.

## J4 — grep gates

Each of these must return zero. Write them to falsify your own work, not to confirm it.

```bash
# the discarding bug and the quiet warning are both gone
git grep -n 'else status' -- services/notification-service
git grep -n 'log write skipped' -- services/notification-service

# no host-wide bind left on the API port
git grep -n '"8108:8108"' -- infra/

# the placeholder key is gone; .env is untracked, so git grep will not see it
grep -n 'INTERNAL_API_KEY' .env
git grep -n 'dev-key-123'
```

The last `git grep` catching a hit in `docs/` or `README.md` is a documentation leak of the old
placeholder — harmless once rotated, but fix the text.

`rg` is not on PATH on this machine; `git grep` is the substitute. Under PowerShell, `curl` is an
alias — use `curl.exe`.

## J5 — regression gates (existing suites only — author nothing new)

`ruff` clean · `mypy` clean on the two touched files · the existing business-api and persistence
suites still pass · `scripts/verify_p0_1.sh` and `scripts/verify_p0_2.sh` still pass. No `tsc` run is
needed — P2-2 touches no frontend file.

`make test` still cannot run end to end: the repo-shipped `.venv` is a broken Linux launcher
(`No module named alembic.__main__`). Run the suites directly, as P1-2, P1-3 and P2-1 all did.

---

# §K — What P2-2 does not close

Carried forward deliberately, so nothing here is mistaken for done:

- **G4** — the four auth mutations remain unaudited until their route bodies are read.
- **R11** — three different definitions of an open invoice still coexist (`customer_360`'s
  `!= "paid"`, `_OPEN_INVOICE_STATUSES`, and `OWED_STATUSES` which includes `disputed`). Closed by
  your decision, not by the code.
- **R12** — the GLPI revert (H-3).
- **R14** — persona contract, 5 FAIL / 43 OK.
- **R15** — lint debt: the mypy `ignore_errors` ratchet across 14 modules, and the ruff burn-down.
  Both are recorded debt, not fixes.
- **H-6** — `knowledge-service` down on the torch hash mismatch. Unrelated to P2-2, but it is why
  `make health` reports 10 of 11.
- **The broken `.venv`** — blocks `make migrate` and `make test`. Every migration so far has needed
  `PYTHONPATH=packages/persistence/src python -m alembic upgrade head`.
- **`billing.accounts` has 2 rows**, so most customers have no `account_number` and
  `/api/v1/me/profile/detail` truthfully returns `null` for them. Real data, not a bug — but the
  portal shows a blank reference for nearly everyone.
- **P1-3 is locally verified, not verified.** No GitHub Actions run has been read: which jobs ran,
  the `test` job duration, whether `knowledge-service` built, whether the push trigger fired on
  `version_*`.
