# P1-2 — Fix Identified Code Inconsistencies

**Branch:** `version_85` @ `752fc4ebb6a80a5dd3f9b93bd50e67c061c8ee21`
**Prerequisites:** P0-1, P0-2, P0-3 applied and green (they are — `verify_p0_1.sh` 20/20, `verify_p0_2.sh` 9/9, business-api 60 passed, worker conversation suite 8 passed).
**Rebuild required:** YES — `agent-worker` AND `business-api`. Both Dockerfiles bake source; a restart is not enough.
**Migration required:** NO. No schema change, no alembic revision. Head stays `0016_portal_identity`.
**New dependencies:** NONE (Python or npm).
**Frontend changes:** NONE.

---

## §1 What P1-2 is

P0-1/P0-2/P0-3 closed the security and data-capture holes. P1-2 closes the gaps where **a mechanism
exists, is wired, is constrained by the database, and is simply never invoked** — the same shape as
P0-3, three more times.

The centrepiece is worth stating plainly, because it is the single largest source of wrong numbers on
the dashboard today:

> `conversation.call_sessions.final_disposition` has a column, a CHECK constraint listing its four
> legal values, a writer parameter, and a persistence branch that assigns it. **Nothing has ever
> passed a value.** All 129 sessions are NULL, and five separate read surfaces are reporting zero or
> `"unknown"` as a result.

This is not a metric bug. Every reader is doing exactly what it was told; the producer never spoke.
The fix is one keyword argument at one call site, plus a pure function that reads state the session
already maintains.

The rest of P1-2 is smaller: a bootstrap that cannot bootstrap, a table that grows forever, and two
honest withdrawals of things I previously claimed were broken and are not.

### 1.1 What this patch does NOT do

- It does not backfill the 129 existing NULL rows. That is a data mutation over historical records
  and needs its own decision (§7.4).
- It does not touch `apps/supervisor-dashboard`. That app is genuinely broken (§7.3) but retiring or
  rewiring an application is an approval decision, not an inconsistency fix.
- It does not change any read query. Every number below becomes correct because the **producer**
  starts writing, not because a reader was rewritten.

---

## §2 Coverage disclosure — what I read for this patch

All reads are from `version_85` at the SHA above. Blob SHAs are recorded so the implementer can
verify nothing moved underneath this document.

| File | Blob SHA | Why |
| --- | --- | --- |
| `apps/agent-worker/src/server.py` | `ad045ea0` | the shutdown call site; P0-3 as-applied |
| `apps/agent-worker/src/conversation/writer.py` | `fbfea025` | `finish_session` signature + the `session_finish` write branch |
| `apps/agent-worker/src/session/session_state.py` | `a852e491` | every field available at shutdown |
| `apps/agent-worker/src/tools/session_flow_tools.py` | `acbed180` | `end_conversation` — the graceful-close signal |
| `apps/agent-worker/src/tools/escalation_tools.py` | `eed74aef` | `escalate_to_manager` — what it sets |
| `apps/agent-worker/src/telephony/sip_transfer.py` | `3ddf8ff4` | `transfer_to_human` — every `human_transfer_outcome` value |
| `apps/agent-worker/src/agents/manager_agent.py` | `3aa30faf` | the escalation target's `on_enter` |
| `apps/business-api/src/business_api/repositories.py` | `7d167c70` | `kpis`, `analytics_trend`, `telemetry_timeline`, `session_list`, `session_detail` |
| `apps/business-api/src/business_api/jobs/retention.py` | `8e6b9322` | what the audited purge covers |
| `apps/business-api/src/business_api/infrastructure/auth/rate_limit.py` | `f81f0aef` | the pruning withdrawal (§7.1) |
| `packages/persistence/src/persistence/models/portal_identity.py` | `10242922` | `PortalSession` columns |
| `packages/persistence/seed/` (listing) | — | exact seed module names |
| `apps/business-api/src/business_api/` (listing) | — | `seed_admin.py` location |
| `Makefile` | `26ea4077` | the `seed` and `frontends` targets |
| `apps/supervisor-dashboard/src/api.ts` | `25dea2e8` | the `X-Role` finding (§7.3) |

**Deliberately NOT read, and therefore not asserted about:**

- `apps/business-api/src/business_api/main.py` — the `/api/v1/jobs/retention` route. §5.4 is written as a
  **read-then-decide gate** for exactly this reason.
- `.env.example` — 17 KB. §6 is a **grep-then-fix gate** rather than a byte-exact diff.
- `apps/business-api/tests/test_retention.py` — §8.3 tells the implementer to read it before adding to it.
- `Frontend/admin_dashboard/src/routes/*` — no frontend file is touched, so no rendering claim is made.

---

## §0 Pre-flight gates

Run every gate. If any fails, STOP and report — do not adapt silently.

**0.1 — Baseline is green.** From repo root:

```bash
bash scripts/verify_p0_1.sh          # expect 20/20
bash scripts/verify_p0_2.sh          # expect 9/9
python -m pytest apps/business-api/tests -q
python -m pytest apps/agent-worker/tests/conversation -q
```

Record the two pytest counts as *your* baseline. Do not compare them to any number in this document —
this cookbook deliberately states no test totals.

**0.2 — The disposition really is never written.** Exactly one production call site:

```bash
git grep -n "finish_session" -- apps packages
```

Expect: the definition in `conversation/writer.py`, the call in `server.py`, and test references only.
If a second production caller exists, STOP — the derivation in §3 assumes one shutdown path.

**0.3 — The database agrees.** Against the running stack:

```bash
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "SELECT final_disposition, count(*) FROM conversation.call_sessions GROUP BY 1;"
```

Expect a single row: `NULL | 129` (the count may differ if new calls landed; the point is that **every**
row is NULL). If any row already has a non-NULL disposition, STOP and report — something else is
writing it and §3 needs rethinking.

**0.4 — The CHECK vocabulary is what §3 targets.**

```bash
git grep -n "final_disposition" -- packages/persistence/src/persistence/models/conversation.py
```

Expect the CHECK to permit exactly `'resolved','escalated','dropped','abandoned'`. §3 emits only
these four strings. If the list differs, STOP.

**0.5 — `conversation_ending` is currently undeclared.**

```bash
git grep -n "conversation_ending" -- apps/agent-worker
```

Expect hits **only** in `tools/session_flow_tools.py` (two: the read and the write), and **none** in
`session/session_state.py`. That absence is the inconsistency §3.2 fixes.

**0.6 — Lint baselines. Record, do not fix.**

```bash
python -m ruff check apps/agent-worker/src        # expect 16
python -m ruff check apps/business-api/src        # expect 11
python -m ruff check apps/business-api/src/business_api/main.py   # expect 7
```

Repo-wide `python -m ruff check .` was 147 at P0-2. That is P1-3's problem, not this patch's. Do not
let it grow.

**0.7 — Makefile whitespace.** Recipe lines in a Makefile MUST begin with a literal TAB, never spaces.
Before editing §4, confirm your editor is not configured to expand tabs in this file:

```bash
git grep -nP "^    \\S" -- Makefile | head
```

Expect **no output** for recipe lines. After your edit, re-run it and expect no output again.

---

## §3 Item A — `final_disposition` is never written

### 3.1 The evidence chain, end to end

Three files, read this turn, form a complete and unbroken chain. Nothing here is inferred.

**Link 1 — the shutdown call site omits the argument.** `server.py`:

```python
    async def _finish_conversation() -> None:
        history = user_data.sentiment_history or [0.0]
        writer.finish_session(
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
        await writer.aclose()
```

**Link 2 — the parameter therefore defaults to `None`.** `writer.py`:

```python
    def finish_session(self, *, disposition=None, max_frustration=0.0, recording_consent=None) -> None:
```

**Link 3 — and `None` is faithfully written to the column.** `writer.py`, `_write`:

```python
            elif kind == "session_finish":
                obj = session.get(CallSession, item["session_db_id"])
                if obj is not None:
                    ...
                    obj.final_disposition = item.get("disposition")
```

Every layer is correct in isolation. The value was simply never supplied.

### 3.2 What it costs — five read surfaces, all read this turn

This is why Item A leads P1-2 rather than sitting in a backlog.

| Surface | Code | Behaviour with all-NULL |
| --- | --- | --- |
| `kpis()` | `count(... final_disposition == "resolved")` and `== "escalated"` | **resolution rate 0 %, escalation rate 0 %** on the main dashboard header |
| `analytics_trend()` | `_bundle()` uses the identical two predicates for the current **and** previous window | **0 % in both windows, delta always 0** — the trend chart cannot ever move |
| `telemetry_timeline()` | `"disposition": s.final_disposition or "unknown"` | **all 50 points read `"unknown"`** |
| `session_list(disposition=…)` | `.where(CallSession.final_disposition == disposition)` | the `/sessions` filter returns **empty for all four values** |
| `session_detail()` | `"disposition": call.final_disposition` | every call detail shows a null disposition |

Note the compounding: `kpis()` and `analytics_trend()` are *independent* implementations of the same
predicate, so fixing a reader would have meant fixing it twice. Fixing the producer fixes all five at
once. That is the argument for doing it at the writer.

### 3.3 Deriving the value — from state the session already keeps

The roadmap forbids inventing behaviour. So the derivation reads **only** fields that
`SessionUserData` already declares and that existing tools already assign. No new signal is created,
no LLM is asked, nothing is guessed.

What the code already sets, confirmed by reading each writer:

| Field | Set by | When |
| --- | --- | --- |
| `human_transfer_outcome` | `sip_transfer.transfer_to_human` | `"callback_only"`, `"no_advisor"`, `"transferred"`, `"transfer_failed"` |
| `escalation_reason` | `sip_transfer.transfer_to_human` | `"sip_unavailable"`, `"no_advisor_available"`, `"transfer_failed"` |
| `conversation_ending` | `session_flow_tools.end_conversation` | `True`, once the caller confirms they need nothing else |
| `caller_turn_index` | `base_agent.on_user_turn_completed` | incremented on every caller utterance |

Mapped onto the CHECK vocabulary:

| Condition (first match wins) | Disposition | Justification |
| --- | --- | --- |
| `human_transfer_outcome` or `escalation_reason` set | `escalated` | the call reached `ManagerAgent`; a transfer or a callback was arranged |
| `conversation_ending` is True | `resolved` | `end_conversation` only runs after the caller confirms nothing else is needed — the closing protocol is the definition of a resolved call |
| `caller_turn_index == 0` | `abandoned` | the caller connected and never spoke |
| otherwise | `dropped` | the caller was engaged and the session ended without a close or an escalation — a hang-up |

**Why escalation is checked first.** A transferred call raises `StopResponse` and the caller's leg is
gone, so `end_conversation` cannot run afterwards — the two are mutually exclusive in practice. The
ordering is belt-and-braces, and it encodes the right priority: if a human was involved, that is the
truth of the call regardless of what happened after.

**Why `dropped` is the fallback, not `resolved`.** Optimism here would be dishonest and would
inflate the very KPI this patch exists to make truthful. A call that ended without the agent closing
it did not demonstrably resolve anything.

### 3.4 Why not derive it in SQL instead

Tempting — `escalation_cases` already has a row per escalation, so `kpis()` could LEFT JOIN it. Rejected:

1. It only distinguishes escalated from not-escalated. `resolved` / `dropped` / `abandoned` have no
   database trace at all; they exist only in session memory at shutdown.
2. It would need writing twice (`kpis` and `analytics_trend`) and would still leave
   `telemetry_timeline`, `session_detail` and the `/sessions` filter reading NULL.
3. It leaves the column permanently empty, so the schema keeps lying about itself.

Write the value once, at the moment it is known.

### 3.5 Edit 1 of 3 — declare `conversation_ending`

`end_conversation` already does `user_data.conversation_ending = True`. `SessionUserData` is a
`@dataclass` **without** `slots`, so assigning an undeclared attribute silently works — which is why
this has never failed. It is still an inconsistency: the dataclass is documented as "session-scoped
state shared by the active persona, tasks and tools", and this piece of state is invisible in it.

**File:** `apps/agent-worker/src/session/session_state.py`

`oldStr`:

```python
    human_transfer_announced: bool = False
    human_transfer_in_progress: bool = False
    human_transfer_outcome: str | None = None
    escalation_reason: str | None = None
```

`newStr`:

```python
    human_transfer_announced: bool = False
    human_transfer_in_progress: bool = False
    human_transfer_outcome: str | None = None
    escalation_reason: str | None = None
    # P1-2 - tools.session_flow_tools.end_conversation already assigns this when the caller
    # confirms they need nothing else. The dataclass has no slots, so the assignment silently
    # created an undeclared attribute; declaring it makes the graceful close visible to type
    # checkers and to _derive_disposition. False = the call did not end through the close tool.
    conversation_ending: bool = False
```

**Scope proof.** A dataclass field with a default, appended after other defaulted fields, cannot break
positional construction. Every existing `SessionUserData(...)` call site uses keywords
(`SessionUserData(language=language)` in `server.py`). `end_conversation`'s
`getattr(user_data, "conversation_ending", False)` keeps working unchanged — it now reads a declared
field instead of a missing one.

### 3.6 Edit 2 of 3 — the derivation helper

**File:** `apps/agent-worker/src/server.py`

Insert a new module-level function **between** `_open_conversation` and the `@server.rtc_session`
decorator. Anchor on the end of `_open_conversation`.

`oldStr`:

```python
    return writer


@server.rtc_session(agent_name=settings.livekit_agent_name.strip())
```

`newStr`:

```python
    return writer


def _derive_disposition(user_data: SessionUserData) -> str:
    """How this call ended, in conversation.call_sessions.final_disposition's own vocabulary.

    P1-2 - the column, its CHECK constraint and the writer parameter all existed, but the single
    shutdown call site never passed a value, so every row was NULL and every disposition-derived
    read (kpis, analytics_trend, telemetry_timeline, session_detail, the /sessions filter)
    reported zero or "unknown". This decides nothing new: it reads state the session already
    maintains and maps it onto the four values the CHECK constraint permits.

    Escalation wins over a graceful close: a completed SIP transfer raises StopResponse and the
    caller's leg is gone, so end_conversation cannot also have run. "dropped" is the fallback
    rather than "resolved" - a call that ended without the agent closing it did not demonstrably
    resolve anything, and guessing otherwise would inflate the very KPI this makes truthful.
    """
    if user_data.human_transfer_outcome or user_data.escalation_reason:
        return "escalated"
    if user_data.conversation_ending:
        return "resolved"
    if user_data.caller_turn_index == 0:
        return "abandoned"
    return "dropped"


@server.rtc_session(agent_name=settings.livekit_agent_name.strip())
```

**Why direct attribute access and not `getattr`.** After Edit 1 all four fields are declared on the
dataclass with defaults, so they always exist. `getattr(..., default)` here would only hide a future
rename behind a silently-wrong disposition. `SessionUserData` is already imported in `server.py`
(`from session import SessionUserData`), so the annotation needs no new import.

### 3.7 Edit 3 of 3 — pass it

**File:** `apps/agent-worker/src/server.py`

`oldStr`:

```python
        writer.finish_session(
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
```

`newStr`:

```python
        writer.finish_session(
            disposition=_derive_disposition(user_data),
            max_frustration=max(0.0, -min(history)),
            recording_consent=user_data.recording_consent,
        )
```

### 3.8 Safety analysis

| Concern | Answer |
| --- | --- |
| Voice path | Untouched. `_finish_conversation` is a shutdown callback; it runs after the room is gone. |
| Can the helper raise? | No. Four attribute reads and three comparisons on a dataclass whose fields all have defaults. No I/O, no await, no imports. |
| Can it return an illegal value? | No. Four `return` statements, four string literals, all in the CHECK list. There is no other exit. |
| Existing rows | Untouched. Only sessions closing after deploy get a value. |
| The writer | Zero changes. `finish_session` already accepts `disposition`; we are using the parameter as designed. |
| Failure mode | Unchanged. The enqueue is `put_nowait`; a DB outage still degrades to a dropped row and a warning. |
| Schema | Zero changes. No migration. |

### 3.9 The seam

Sessions closed **before** this deploy stay NULL; sessions closed **after** carry a disposition. So
for a period, `kpis()` reports a resolution rate over a denominator of all 129+ sessions while only
the new ones can contribute to the numerator — the rate will look low and climb. Record the deploy
timestamp in the results document and state it beside any KPI screenshot. §7.4 covers the backfill
decision that would close the seam.

---

## §4 Item B — `make seed` cannot produce a login

### 4.1 The inconsistency

P0-1 made authentication mandatory. The bootstrap was never updated to match. Current `Makefile`:

```make
seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference
```

And `dev: install infra migrate seed`. So the documented one-command setup produces a database with
customers and catalogs but **no `auth.portal_accounts` row of any kind** — nobody can sign in to the
admin dashboard, and no caller can pass CIN verification on a voice call. Both seeders exist and
neither is invoked:

- `packages/persistence/seed/seed_auth_credentials.py` — CIN last-4 credentials for voice identity.
- `apps/business-api/src/business_api/seed_admin.py` — the idempotent admin login (created by P0-1).

### 4.2 The edit

**File:** `Makefile`

> **TAB WARNING.** Both recipe lines below begin with a literal TAB. If your editor inserts spaces,
> `make` fails with `*** missing separator`. Re-run gate 0.7 after editing.

`oldStr`:

```make
seed:  ## Seed pilot callers + reference catalogs
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference
```

`newStr`:

```make
seed:  ## Seed pilot callers + reference catalogs + the logins P0-1 made mandatory
	cd packages/persistence && $(PYTHON) -m seed.seed_pilot && $(PYTHON) -m seed.seed_reference && $(PYTHON) -m seed.seed_auth_credentials
	$(PYTHON) -m business_api.seed_admin
```

### 4.3 Why this shape

- `seed_auth_credentials` lives in the same `seed` package as the other two, so it joins the existing
  `cd packages/persistence &&` chain and needs no path handling.
- `seed_admin` lives in `business_api`, which `make install` pip-installs editable
  (`-e ./apps/business-api`), so `python -m business_api.seed_admin` resolves from any working
  directory. It gets its own recipe line, outside the `cd`, because the `cd` only applies to the line
  it appears on.
- `seed_admin` is idempotent by construction (P0-1), so re-running `make seed` is safe.
- The two existing seeders are untouched, in order, on the same line as before.

### 4.4 Prerequisite the implementer must confirm

`seed_admin` reads `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_ROLE` from the environment. Those are
the **backend** variables that P0-1 introduced and that P0-2 deleted from the *frontend* config —
different things with similar names. Before running, confirm they are present in the repo-root `.env`:

```bash
grep -nE "^ADMIN_(EMAIL|PASSWORD|ROLE)=" .env
```

If absent, `make seed` will fail loudly at the new line rather than silently producing no admin —
which is the correct behaviour, but note it in the results so it is not read as a regression.

### 4.5 The `frontends` target — flagged, NOT changed

While reading the Makefile:

```make
frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install
```

It installs the two apps nobody uses and **not** the two that are actually shipped
(`Frontend/admin_dashboard`, `Frontend/customer_portal`). This is a real inconsistency, but it is
entangled with the retire-or-rewire decision in §7.3, so **make no change here in this patch.**
Record it and move on.

---

## §5 Item C — `auth.portal_sessions` grows forever

### 5.1 The inconsistency

P0-1 made browser sessions real: every login writes an `auth.portal_sessions` row holding a token
digest, an expiry and an optional revocation timestamp. That is exactly right — it is what makes
logout and expiry server-side facts rather than cosmetics.

But nothing ever deletes those rows. The platform's one purge job, `jobs/retention.py`, was written
before P0-1 existed and covers only conversation data:

```python
def run_retention(session: Session, retention_days: int = 90, dry_run: bool = True) -> RetentionReport:
    """Anonymize transcripts + clear audio pointers for sessions older than the window (audited)."""
```

It touches `Turn.transcript_masked` and `CallSession.audio_record_url`. `portal_sessions` is not in
the file. Every login, every token refresh, every logout leaves a permanent row.

This is low-severity today (the live table holds 6 rows) and unbounded over time. It belongs in P1-2
precisely because the correct home for it already exists and is already audited.

### 5.2 Design

**Only remove rows that can no longer authenticate anything.** `portal_auth` checks `expires_at` and
`revoked_at` on every request, so an expired or revoked row is already dead weight — deleting it
changes no behaviour whatsoever.

**Keep a forensic grace window.** Deleting a session the instant it expires destroys the evidence of
a login that an investigation might need. Seven days.

**Do not touch the existing block.** The new purge is a separate, independently-guarded block placed
after the existing one, with its own audit entry and its own commit. The conversation-retention logic
is not modified, re-indented, or re-ordered — the diff adds lines and changes none.

**Two different horizons, deliberately.** Call data is purged at 90 days; sessions at expiry + 7
days. They are unrelated lifecycles and must not share a constant.

### 5.3 The edits

**File:** `apps/business-api/src/business_api/jobs/retention.py`

**Edit C-1 — imports.**

`oldStr`:

```python
from object_storage import get_store
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.conversation import CallSession, Turn

_PURGED = "[purged]"
```

`newStr`:

```python
from object_storage import get_store
from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.conversation import CallSession, Turn
from persistence.models.portal_identity import PortalSession

_PURGED = "[purged]"

# P1-2 - auth.portal_sessions is the one table P0-1 added that grows without bound. A row whose
# expires_at has passed, or which was revoked at logout, can no longer authenticate anything
# (portal_auth checks both on every request), so removing it changes no behaviour. The grace
# window keeps a logout or an expiry visible to an investigation for a week first. This is a
# separate horizon from the conversation retention window on purpose: unrelated lifecycles.
_SESSION_GRACE_DAYS = 7
```

**Edit C-2 — the report field.**

`oldStr`:

```python
    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool
```

`newStr`:

```python
    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool
    portal_sessions_purged: int = 0
```

A defaulted field appended last cannot break any existing construction — and the sole existing
construction already uses keywords.

**Edit C-3 — the purge block.** Anchor on the return statement so the existing block is provably
untouched.

`oldStr`:

```python
    return RetentionReport(
        cutoff=cutoff.isoformat(), sessions_matched=matched,
        turns_anonymized=turns_anonymized, dry_run=dry_run,
    )
```

`newStr`:

```python
    portal_sessions_purged = 0
    if not dry_run:
        session_cutoff = datetime.now(UTC) - timedelta(days=_SESSION_GRACE_DAYS)
        purged = session.execute(
            delete(PortalSession).where(
                or_(
                    PortalSession.expires_at < session_cutoff,
                    PortalSession.revoked_at < session_cutoff,
                )
            )
        )
        portal_sessions_purged = purged.rowcount or 0
        if portal_sessions_purged:
            PgAuditLedger(session).append(
                None, "data_retention",
                {
                    "cutoff": session_cutoff.isoformat(),
                    "portal_sessions_purged": portal_sessions_purged,
                },
                entity_reference="retention_job",
            )
        session.commit()

    return RetentionReport(
        cutoff=cutoff.isoformat(), sessions_matched=matched,
        turns_anonymized=turns_anonymized, dry_run=dry_run,
        portal_sessions_purged=portal_sessions_purged,
    )
```

### 5.4 Two details that matter

**`revoked_at < session_cutoff` needs no NULL guard.** In SQL, `NULL < timestamp` evaluates to NULL,
not true, so `or_` never selects an unrevoked row on that arm. Adding `is_not(None)` would be
redundant noise.

**`datetime`, `UTC` and `timedelta` are already imported** at the top of the file
(`from datetime import UTC, datetime, timedelta`). Do not add an import.

### 5.5 GATE — the route may or may not need a key

I did **not** read `main.py`. The `/api/v1/jobs/retention` route serialises `RetentionReport` somehow,
and which way it does that decides whether the new count is visible.

```bash
git grep -n "retention" -- apps/business-api/src/business_api/main.py
```

Read the handler, then:

- If it returns `report.__dict__`, `dataclasses.asdict(report)`, or the dataclass directly — **do
  nothing.** The key appears automatically. This is an additive JSON key, the same precedent as
  FEATURE_21's `outstanding`.
- If it builds a dict with explicit keys — add `"portal_sessions_purged": report.portal_sessions_purged`
  alongside the existing ones. Change nothing else in the handler.

Report which branch you found. Do not guess.

---

## §6 Item D — `.env.example` points `BUSINESS_API_URL` at the wrong port (verify first)

My notes record `BUSINESS_API_URL=http://localhost:8107` in `.env.example`. 8107 is **token-service**;
business-api listens on **8108** (`apps/business-api/Dockerfile`: `--port 8108`; compose publishes
`"8108:8108"`). I have not re-read the 17 KB file at `version_85`, so this is a gate, not an assertion.

```bash
git grep -n "BUSINESS_API_URL" -- .env.example
```

- **No hits, or already `8108`** — nothing to do. Record it as withdrawn and move on.
- **`http://localhost:8107`** — change that one occurrence to `http://localhost:8108` and append a
  trailing comment on the same line or the line above:
  `# business-api listens on 8108; 8107 is token-service.`

**Do not touch any other line, and do not touch `.env`.** Check whether the agent-worker override in
`docker-compose.apps.yml` (`BUSINESS_API_URL: "http://business-api:8108"`) is present and correct
while you are there — it was at `version_83` — and report, but change nothing there.

---

## §7 Findings that are NOT changed by this patch

This section exists so nothing quietly disappears. Three withdrawals and three gated decisions.

### 7.1 WITHDRAWN — "the rate-limit store is never pruned"

I carried this in the backlog since P0-1. **It is wrong.** `infrastructure/auth/rate_limit.py` has a
`_prune(now)` that drops every bucket whose newest hit is older than the window, plus an LRU-style
cap:

```python
_MAX_TRACKED_KEYS = 4096
...
def check(key: str, *, limit: int = MAX_ATTEMPTS, window: float = WINDOW_SECONDS) -> bool:
    now = time.monotonic()
    with _lock:
        _prune(now)
```

`_prune` runs on **every** `check()`. The store is bounded in both time and cardinality. No change,
and the backlog item is closed as unfounded.

The module's own docstring also already documents the multi-worker caveat and names the durable
`locked_until` lockout as the layer that actually stops a targeted attack. Nothing to add.

### 7.2 WITHDRAWN — `session_list.turn_count` "double counts"

Carried forward from P0-3 §6.2. Confirmed by reading `session_list`: it counts all turns for a
session with no speaker predicate, so it does now include agent rows. But:

- the field is named `turn_count`, not `caller_turn_count` — counting all turns is what it says;
- P0-3's label gate established it has **no render consumer** on the admin dashboard.

A correct, unrendered field is not a defect. **No change.** If a UI ever surfaces it, the label must
say "Turns", not "Caller turns" — recorded for P2-1.

### 7.3 GATED DECISION — `apps/supervisor-dashboard` is dead

Confirmed at `version_85` by reading `src/api.ts` (blob `25dea2e8`):

```ts
const ROLE = import.meta.env.VITE_API_ROLE ?? "administrateur";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "X-Role": ROLE } });
```

Every one of its 18 endpoints sends `X-Role` and **no `Authorization` header at all**. Since P0-1,
`security.py` resolves the role only from a principal, so all 18 return 401. The app cannot show a
single number. It also carries the exact anti-pattern P0-2 removed everywhere else: a client-side
role default.

It is not a compose service, so nothing in the running stack depends on it. It is referenced by the
Makefile `frontends` target (§4.5).

**Three options, none taken in this patch:**

| Option | Cost | Consequence |
| --- | --- | --- |
| Retire it (delete, or move under `archive/`) | small | removes a dead app and the last `X-Role` sender; irreversible without git history |
| Rewire to bearer sessions | large | a third implementation of P0-1 login, session cookie and role gating, for an app that duplicates the admin dashboard's read surface |
| Leave, document | none | a broken app stays in the tree and in `make frontends` |

**My recommendation: retire it**, and fix `make frontends` to install the two apps that actually ship.
The admin dashboard already covers its entire read surface. But §0 of the roadmap forbids deleting
without approval, so **this patch changes nothing here.** Awaiting a decision.

### 7.4 GATED DECISION — backfilling the 129 NULL dispositions

After Item A, new calls carry a disposition and old ones stay NULL (§3.9). A backfill could
reconstruct `escalated` from `conversation.escalation_cases` (58 rows, all open, all targeting
`manager_agent`), but `resolved` / `dropped` / `abandoned` **cannot be reconstructed** — the signals
lived only in session memory, which is gone.

So a backfill would set `escalated` on the sessions that escalated and leave the rest NULL. That is
honest but partial, and it writes historical rows. **Not done here.** Options if you want it: mark
only the provable `escalated` rows; or leave history NULL and treat the deploy timestamp as the start
of measurement. My recommendation is the second — it needs no data mutation and no explaining.

### 7.5 RECORDED — `item.interrupted` still not stored

P0-3 §6.3 deliberately skipped it: `ChatMessage.interrupted` is real, but `conversation.turns` has no
column for it, and adding one means a migration. Still out of scope. It would tell you which agent
replies the caller talked over — genuinely useful for quality scoring. Candidate for P2-2.

### 7.6 RECORDED — `system_overview()`'s eleven hardcoded `"online"` strings

Still present at `version_85`, still literal strings rather than probes. The admin dashboard's
overview page does not render the status field (established earlier, and the reason rule 1.4 exists).
I have **not** read the supervisor dashboard's renderer, and since §7.3 leaves that app untouched and
non-functional anyway, no claim is made about it. Fixing this properly means real health probes —
that is runbook item D6, not an inconsistency fix. **No change.**

---

## §8 Tests

Two new files. Both offline, deterministic, no LiveKit, no network. Written so they will pass under
CI once P1-3 adds `apps/agent-worker` to the test job.

### 8.1 `apps/agent-worker/tests/conversation/test_disposition.py` (new)

Directory exists (P0-3 gate 0.5 confirmed it). Import style: **`from conftest import ...` never
`from tests.conftest import ...`** — binding convention from P0-1.

```python
"""P1-2 - the disposition derived at shutdown must be truthful and always legal.

Pure unit tests over _derive_disposition: no LiveKit, no event loop, no database. The function
is a pure map from SessionUserData to one of the four values conversation.call_sessions'
CHECK constraint permits, so it can be tested exactly.
"""
from __future__ import annotations

import pytest

from server import _derive_disposition
from session import SessionUserData

# The CHECK constraint on conversation.call_sessions.final_disposition.
LEGAL = {"resolved", "escalated", "dropped", "abandoned"}


def test_graceful_close_is_resolved():
    user_data = SessionUserData()
    user_data.caller_turn_index = 4
    user_data.conversation_ending = True
    assert _derive_disposition(user_data) == "resolved"


def test_transfer_outcome_is_escalated():
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.human_transfer_outcome = "transferred"
    assert _derive_disposition(user_data) == "escalated"


def test_escalation_reason_alone_is_escalated():
    """transfer_to_human sets escalation_reason on every failure path."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.escalation_reason = "no_advisor_available"
    assert _derive_disposition(user_data) == "escalated"


def test_escalation_beats_graceful_close():
    """If a human was involved, that is the truth of the call."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 6
    user_data.conversation_ending = True
    user_data.human_transfer_outcome = "callback_only"
    assert _derive_disposition(user_data) == "escalated"


def test_silent_caller_is_abandoned():
    assert _derive_disposition(SessionUserData()) == "abandoned"


def test_engaged_then_gone_is_dropped():
    """The pessimistic fallback: never call an unclosed call resolved."""
    user_data = SessionUserData()
    user_data.caller_turn_index = 3
    assert _derive_disposition(user_data) == "dropped"


@pytest.mark.parametrize(
    "turns,ending,outcome,reason",
    [
        (0, False, None, None),
        (0, True, None, None),
        (5, False, None, None),
        (5, True, None, None),
        (5, False, "no_advisor", None),
        (5, False, None, "sip_unavailable"),
        (0, True, "transferred", "transfer_failed"),
    ],
)
def test_every_combination_is_a_legal_value(turns, ending, outcome, reason):
    """The function must never be able to violate the CHECK constraint."""
    user_data = SessionUserData()
    user_data.caller_turn_index = turns
    user_data.conversation_ending = ending
    user_data.human_transfer_outcome = outcome
    user_data.escalation_reason = reason
    assert _derive_disposition(user_data) in LEGAL


def test_conversation_ending_is_a_declared_field():
    """P1-2 edit 1: it must be a real dataclass field, not an attribute set by accident."""
    assert "conversation_ending" in SessionUserData.__dataclass_fields__
    assert SessionUserData().conversation_ending is False
```

**Import path note.** The worker's tests already import worker modules by top-level name
(`from session import ...`), because `apps/agent-worker/src` is on the path via the editable install.
If `from server import _derive_disposition` fails to resolve in your environment, **stop and report
it** rather than adding a `sys.path` hack — tell me and I will re-anchor the test.

### 8.2 The deliberate red

`test_conversation_ending_is_a_declared_field` **must fail before Edit 1** (`KeyError`/assertion on
`__dataclass_fields__`) and every other test in the file must fail before Edits 2–3 (`ImportError` on
`_derive_disposition`). Run the file once before applying §3 and record the failure. A test that was
never red proves nothing.

### 8.3 `apps/business-api/tests/test_retention_portal_sessions.py` (new)

**Read `apps/business-api/tests/test_retention.py` first** and mirror its fixtures and construction
style exactly — do not invent a new harness. The assertions to add:

1. **Dry run purges nothing.** Insert a `PortalAccount` plus a `PortalSession` with
   `expires_at = now - 30 days`; call `run_retention(session, dry_run=True)`; assert the row still
   exists and `report.portal_sessions_purged == 0`.
2. **A long-expired session is purged.** Same row; `dry_run=False`; assert it is gone and the count
   is 1.
3. **A live session survives.** `expires_at = now + 1 day`; `dry_run=False`; assert it still exists.
4. **Inside the grace window survives.** `expires_at = now - 1 day` (grace is 7); `dry_run=False`;
   assert it still exists. *This is the test that proves the constant is honoured rather than ignored.*
5. **A long-revoked session is purged** even though `expires_at` is in the future — proves the `or_`
   arm works.
6. **Positive control:** assert the pre-existing conversation-retention behaviour still reports its
   own `sessions_matched` / `turns_anonymized` from the same call, so a passing purge test cannot mask
   a broken existing block.

`PortalSession.account_id` is NOT NULL with an FK to `auth.portal_accounts`, so every test must create
an account first. `PortalAccount` requires `kind`, `email`, `password_hash`, `password_params`, `role`,
and must satisfy the `kind_role_customer` CHECK — the simplest legal row is
`kind="staff"`, `customer_id=None`, `role="conseiller"`. Use a unique email per test
(`uq_portal_accounts_email`).

---

## §9 Verification

### 9.1 Static

```bash
python -m ruff check apps/agent-worker/src           # must equal the 0.6 baseline (16)
python -m ruff check apps/business-api/src           # must equal the 0.6 baseline (11)
python -m ruff check apps/agent-worker/tests/conversation/test_disposition.py
python -m ruff check apps/business-api/tests/test_retention_portal_sessions.py
python -m pytest apps/agent-worker/tests/conversation -q
python -m pytest apps/business-api/tests -q
bash scripts/verify_p0_1.sh          # must stay 20/20
bash scripts/verify_p0_2.sh          # must stay 9/9
make -n seed                         # must print four commands, no 'missing separator'
```

Both suites must **increase and stay green**. Do not state a total — report your own before/after.

### 9.2 Rebuild

Both images bake source:

```bash
docker compose -p docker-compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml build agent-worker business-api
docker compose -p docker-compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml up -d --no-deps --no-build agent-worker business-api
```

A full `build` still fails on `knowledge-service` (pre-existing torch hash mismatch, recorded at
P0-3). Build only these two. Confirm `business-api` `/health` 200 and fresh worker plugin
registrations in the logs.

### 9.3 The honest live proof for Item A

A real voice call is not reliably available (the worker shows intermittent DNS flapping to
`livekit.cloud`, pre-existing). So prove the write path the same way P0-3 did — in-container, against
the real database:

1. From inside the `agent-worker` container, build a `SessionUserData`, set
   `caller_turn_index = 2` and `conversation_ending = True`, and assert `_derive_disposition` returns
   `"resolved"`.
2. In the same process, open a `ConversationWriter`, `start_session(...)`, then
   `finish_session(disposition="resolved", max_frustration=0.0)`, and `aclose()`.
3. Query Postgres and confirm the row's `final_disposition` is `resolved` — **this is what proves the
   value satisfies the CHECK constraint in the real database**, which no unit test can prove.
4. Repeat once with `"abandoned"` to exercise a second branch.
5. **Delete the probe rows.** `DELETE`, never `TRUNCATE` (hazard H-2). Verify the count returns to its
   pre-probe value and record both numbers.

### 9.4 The read surfaces

Before and after the probe, with an authenticated admin token:

```bash
curl.exe -s -H "Authorization: Bearer $TOKEN" http://localhost:8108/api/v1/kpis
curl.exe -s -H "Authorization: Bearer $TOKEN" "http://localhost:8108/api/v1/sessions?disposition=resolved"
```

With the probe row present, the `disposition=resolved` filter must return it — that proves the
`/sessions` filter is alive again. After cleanup it returns empty again. Record both.

> Use `curl.exe`, not `curl`. PowerShell aliases `curl` to `Invoke-WebRequest`, which mangles
> single-character flags and JSON bodies.

### 9.5 Item C live check

```bash
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom -c \
  "SELECT count(*) FROM auth.portal_sessions;"
curl.exe -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8108/api/v1/jobs/retention?dry_run=true"
```

The live table holds a handful of rows, all recent, so a real run should purge **0** — which is the
correct and expected result. Confirm the response carries `portal_sessions_purged` (per the §5.5
gate), that the count is 0, and that **no row disappeared**. The purge behaviour itself is proven by
the unit tests in §8.3, not by this call. Note the exact route/verb/params you used, since §5.5 is the
first time this route is exercised in a patch.

---

## §10 Apply order

1. Gates §0.1–0.7. Record every baseline.
2. Write `test_disposition.py` (§8.1). Run it. **Confirm it is red.** Record the failure.
3. Edit 1 — `session_state.py` (§3.5).
4. Edit 2 — `server.py` helper (§3.6).
5. Edit 3 — `server.py` call site (§3.7).
6. Re-run `test_disposition.py`. **Green.**
7. `Makefile` (§4.2), then gate 0.7 again, then `make -n seed`.
8. `retention.py` C-1, C-2, C-3 (§5.3). Resolve the §5.5 route gate.
9. Write and run `test_retention_portal_sessions.py` (§8.3).
10. `.env.example` grep gate (§6).
11. Full static suite (§9.1).
12. Rebuild both images (§9.2), then live proofs §9.3–9.5.
13. Clean up every probe row. Verify counts returned to baseline.
14. Write the completion report (§15).

---

## §11 Rollback

Every change is independently revertible; nothing is ordered against anything else.

| Change | Revert |
| --- | --- |
| Item A | Remove `disposition=` from the call. Column returns to NULL for new calls; existing values are legal and harmless. |
| Edit 1 | Remove the field. `end_conversation`'s `getattr` default keeps working. |
| Item B | Restore the two-line recipe. |
| Item C | Remove the block, the field, the constant and the two imports. Purged rows are unrecoverable — but they were expired or revoked and could not authenticate anything. |
| Item D | One-token revert. |

No migration, so no downgrade path is needed.

---

## §12 Impact analysis

**Behaviour that changes:** call sessions closing after deploy carry a disposition; five read surfaces
start returning real values; `make seed` creates logins; expired portal sessions are purged on a
retention run.

**Behaviour that does not change:** the voice path (no edit runs while a call is live — the helper
runs in a shutdown callback); every existing query; every frontend file; the writer; the schema;
authentication; the audit chain's contents beyond one additional `data_retention` entry when rows are
actually purged.

**Risk register:**

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A disposition value violates the CHECK | very low | four literals, all verified against the constraint; §8.1 parametrised test; §9.3 proves it against the real database |
| The derivation mislabels a call | low | it maps existing signals only; `dropped` is the pessimistic default; no KPI is inflated by a guess |
| Makefile tab damage | medium | gates 0.7 and `make -n seed` |
| The purge deletes a usable session | very low | only `expires_at`/`revoked_at` older than expiry + 7 days; both already rejected by `portal_auth` |
| KPI appears to "jump" after deploy | certain | §3.9 seam; state the deploy timestamp beside any figure |

---

## §13 Confidence

| Item | Confidence | Basis |
| --- | --- | --- |
| A — root cause | **Very high** | three-link chain read this turn in three files; database state confirms it |
| A — blast radius | **Very high** | all five surfaces read byte-exact in `repositories.py` |
| A — derivation | **High** | every signal traced to the tool that assigns it; the ordering rationale is stated and testable |
| B | **Very high** | both seeders located; `dev` depends on `seed`; the only risk is whitespace |
| C | **High** | model read byte-exact; additive block; the `main.py` unknown is an explicit gate |
| D | **Gate, not a claim** | not re-read at `version_85` |
| 7.1 / 7.2 withdrawals | **Very high** | both read this turn; both previous claims were wrong |
| 7.3 supervisor-dashboard | **Very high** on the diagnosis, **decision pending** on the remedy |

---

## §14 File manifest — authoritative

**Modified (4, or 5 if the §5.5 gate says so):**

1. `apps/agent-worker/src/session/session_state.py` — one field + comment
2. `apps/agent-worker/src/server.py` — one helper + one argument
3. `apps/business-api/src/business_api/jobs/retention.py` — imports, one field, one block
4. `Makefile` — the `seed` recipe
5. *(conditional)* `apps/business-api/src/business_api/main.py` — one dict key, only if §5.5 requires it
6. *(conditional)* `.env.example` — one port, only if §6 finds 8107

**Created (2):**

1. `apps/agent-worker/tests/conversation/test_disposition.py`
2. `apps/business-api/tests/test_retention_portal_sessions.py`

**Explicitly NOT touched:** `conversation/writer.py` · `base_agent.py` · `repositories.py` ·
`security.py` · any model · any alembic revision · any file under `Frontend/` ·
`apps/supervisor-dashboard/**` · `apps/client-widget/**` · `status.ts` · `pyproject.toml` ·
`package.json` · `.env` · `nginx.conf` · `ci.yml`.

If you touch anything outside this list, stop and report before continuing.

---

## §15 Completion report to return

1. Every §0 gate with its observed value — especially 0.3 (the NULL count) and 0.6 (three ruff numbers).
2. **Proof of the deliberate red** in §8.2: the failure output before Edits 1–3.
3. Both pytest counts, before and after. No total from this document to compare against.
4. The §5.5 gate result: which serialisation branch `main.py` uses, and whether you edited it.
5. The §6 gate result: what `.env.example` actually said.
6. §9.3 probe output — the rows written, the dispositions observed, and the cleanup counts proving
   the database returned to its pre-probe state.
7. §9.4 before/after for `/api/v1/kpis` and the `disposition=resolved` filter.
8. §9.5 `portal_sessions` count before and after, and confirmation that nothing was purged.
9. The deploy timestamp, for the §3.9 seam.
10. `make -n seed` output and confirmation gate 0.7 still passes.
11. Any deviation, with the reason. If this document is wrong, say so plainly — four of my defects have
    been caught this way already and every catch was correct.

---

## §16 Handoff — what P1-3 inherits

P1-3 is CI. Three defects are already measured and waiting:

- `lint` runs `ruff check .` repo-wide; the repo-wide count was **147** at P0-2, so that job is red.
- The `test` job loops packages and services but **omits `apps/agent-worker`** entirely. Both worker
  test files added by P0-3 and P1-2 are deliberately offline and deterministic, so they will pass the
  moment the loop includes them.
- The `docker-build` matrix uses `file: services/${{ matrix.service }}/Dockerfile` for three apps that
  live under `apps/`.

Still open after P1-2: the §7.3 supervisor-dashboard decision (and the `make frontends` fix that
depends on it) · the §7.4 backfill decision · `item.interrupted` (§7.5) · health probes for
`system_overview` (§7.6 / runbook D6) · the portal's remaining `/me/*` surfaces so a signed-in client
stops seeing the **Amara Osei** fixture · the 60 pre-existing portal prettier errors · `CORS_ORIGINS`
versus the real dev ports · whether authentication events belong in `audit.audit_ledger` · `nginx -t`
never run · `infra/helm/telecom-platform/**` never read in full.

---

# AMENDMENT — two decisions returned, both now in scope

> **This block supersedes §4.5, §7.3, §7.4 and the §14 manifest.** Where they say "no change in this
> patch", read §17 and §18 instead. Everything else in the document stands unchanged.
>
> - §7.3 supervisor-dashboard — **APPROVED: retire it.** See §17.
> - §7.4 backfill — delegated to me. **Decision: provable-only backfill.** See §18, including why I
>   revised my own earlier recommendation.
>
> **Revised manifest.** Add to "Modified": `Makefile` (`frontends` + `frontends-clean`, on top of the
> §4.2 `seed` edit). Add to "Created": `scripts/backfill_p1_2_dispositions.sql`. Add to "Deleted":
> `apps/supervisor-dashboard/**`. Remove `apps/supervisor-dashboard/**` from "Explicitly NOT touched";
> `apps/client-widget/**` stays on that list.

---

## §17 Retire `apps/supervisor-dashboard`

### 17.1 Why this is safe — verified, not assumed

Three facts established by reading `version_85` directly:

1. **Nothing builds it.** Its directory listing is `.env.example`, `README.md`, `index.html`,
   `package.json`, `package-lock.json`, `src/`, `tsconfig.json`, `vite.config.ts`. **There is no
   Dockerfile.**
2. **CI never mentions it.** `docker-build-apps` builds `token-service`, `business-api`,
   `agent-worker`. `docker-build` and `security-scan` share a nine-entry matrix of services plus those
   same three apps. `supervisor-dashboard` is in none of them.
3. **It is not a compose service**, so nothing in the running stack imports, proxies or depends on it.

Its only live reference is the `Makefile`, fixed in 17.3.

And it does not work: every one of its 18 endpoints sends `X-Role` with no `Authorization` header, so
since P0-1 all 18 return 401. It also hardcodes `VITE_API_ROLE ?? "administrateur"` — the exact
client-side role default P0-2 eliminated everywhere else. Retiring it removes the last `X-Role`
sender in the repository.

### 17.2 GATE — find every reference before deleting anything

Do this **first**, and report the full output:

```bash
git grep -n "supervisor-dashboard" -- . ':!apps/supervisor-dashboard' ':!**/package-lock.json'
git grep -rn "supervisor_dashboard\|VITE_API_ROLE" -- . ':!apps/supervisor-dashboard'
```

**Expected:** hits in `Makefile` (four lines, fixed in 17.3) and possibly in prose — `README.md`,
`docs/**`, `answers.md`, `features_to_apply/**`. Documentation hits are fine; leave historical
documents alone, they are a record of what was true when written.

**If you find a hit in any of these, STOP and report before deleting:**
`infra/docker-compose/*.yml` · `.github/workflows/*` · `deploy/**` · `infra/helm/**` · `Procfile` ·
`scripts/*.py` · `nginx.conf` · any file under `Frontend/`. My three facts above predict zero hits
there. If reality disagrees, reality wins and I need to re-plan.

### 17.3 Edit — `Makefile`, both frontend targets

The current targets install the two apps nobody ships and neither of the two that ship.

> **TAB WARNING** applies again — every recipe line starts with a literal TAB. Re-run gate 0.7 after.

`oldStr`:

```make
frontends:  ## npm install both web apps
	cd apps/supervisor-dashboard && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS (fixes Rollup optional deps)
	cd apps/supervisor-dashboard && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install
```

`newStr`:

```make
frontends:  ## npm install the shipped web apps (admin dashboard + customer portal)
	cd Frontend/admin_dashboard && npm install
	cd Frontend/customer_portal && npm install
	cd apps/client-widget && npm install

frontends-clean:  ## Reinstall frontend deps for the current OS (fixes Rollup optional deps)
	cd Frontend/admin_dashboard && rm -rf node_modules && npm install
	cd Frontend/customer_portal && rm -rf node_modules && npm install
	cd apps/client-widget && rm -rf node_modules && npm install
```

**`apps/client-widget` is deliberately kept.** Only supervisor-dashboard was approved for retirement,
and I have never read client-widget. Rule 1.4: I will not act on an app whose code I have not
inspected. It stays exactly as it is, in the Makefile and on disk.

### 17.4 Edit — delete the app

```bash
git rm -r apps/supervisor-dashboard
```

Use `git rm`, not a filesystem delete, so the removal is staged as a deletion rather than showing up
as untracked noise.

**Recovery is one command** — the branch is pushed, so the app is permanently recoverable:

```bash
git checkout 752fc4ebb6a80a5dd3f9b93bd50e67c061c8ee21 -- apps/supervisor-dashboard
```

Put that line in the results document and in the version notes. "Retired" must not come to mean
"lost".

### 17.5 Verification

```bash
git grep -n "supervisor-dashboard" -- . ':!**/package-lock.json' ':!docs' ':!features_to_apply'
make -n frontends
make -n frontends-clean
git grep -rn "X-Role" -- apps Frontend packages services
```

- First: no hits outside documentation.
- Second and third: three `cd` lines each, pointing at directories that exist.
- Fourth: **this is the satisfying one.** `X-Role` should now survive only in `security.py`'s history
  comments and P0-2's test/verify scripts — no client anywhere still sends it. Report the exact hits.

Then confirm nothing else regressed: `verify_p0_1.sh` 20/20, `verify_p0_2.sh` 9/9, both pytest suites
green. None of them touch this app, so any change here is a real signal.

---

## §18 Backfill — provable values only

### 18.1 The decision, and why I changed my mind

In §7.4 I recommended no backfill. **I am revising that**, because your criterion — nothing left
non-functional — exposes a cost I had under-weighted: leaving all 129 rows NULL means the `/sessions`
disposition filter stays permanently empty for history, and the platform's **58 escalations become
unfindable through the UI forever**. That is a broken surface, not merely a missing number.

But a *full* backfill would require inventing `resolved` and `dropped`, and inventing data to make a
KPI look complete is precisely the failure mode this project forbids.

So: **backfill exactly what the database can prove, and leave the rest honestly NULL.**

| Value | Recoverable? | Proof |
| --- | --- | --- |
| `escalated` | **Yes** | `conversation.escalation_cases` holds a row per escalation with `session_id`. 58 rows. |
| `abandoned` | **Yes** | a session with zero caller turns is a caller who never spoke. Directly observable. |
| `resolved` | **No** | depended on `conversation_ending`, which lived only in session memory. Gone. |
| `dropped` | **No** | same. It is the *absence* of a signal, and absence cannot be distinguished from `resolved` after the fact. |

Every value written is derived from a persisted row. Nothing is guessed. The unknowable remainder
stays NULL, and `telemetry_timeline()` already renders NULL as `"unknown"` — which is the true answer.

### 18.2 Why `abandoned` is provable in both eras

Careful point. Before P0-3 only caller turns were persisted; after P0-3, agent turns are too. So
"zero rows in `conversation.turns`" means different things either side of the seam. The predicate
therefore counts **caller turns specifically**:

```sql
NOT EXISTS (SELECT 1 FROM conversation.turns t
            WHERE t.session_id = s.id AND t.speaker = 'caller')
```

That is correct in both eras and matches `_derive_disposition`'s own `caller_turn_index == 0` rule
exactly — the backfill and the live derivation agree by construction, which is the property that
matters.

### 18.3 The script

**Create:** `scripts/backfill_p1_2_dispositions.sql`

Same precedent as `scripts/prove_p0_1_data_integrity.sql` — a reviewable SQL file, **not** an alembic
migration. This is data, not schema; it must be readable, dry-runnable and re-runnable.

```sql
-- P1-2 backfill: give historical call sessions the disposition the database can prove.
--
-- Writes ONLY values derivable from persisted rows:
--   escalated -> an escalation case exists for the session
--   abandoned -> the caller never spoke (zero caller turns)
-- Sessions that ended without either signal stay NULL: whether they were resolved or dropped
-- depended on in-memory session state that no longer exists, and guessing would inflate the very
-- KPI this patch exists to make truthful.
--
-- Idempotent: every UPDATE is guarded by final_disposition IS NULL, so re-running is a no-op and
-- no row written by the agent is ever overwritten.
--
-- DELIBERATELY does NOT write to audit.audit_ledger. That chain's hashes are computed in Python by
-- PgAuditLedger under pg_advisory_xact_lock(8472); appending a row from raw SQL would produce an
-- entry whose hash does not chain, permanently breaking integrity verification. The record of this
-- operation is the results document plus the reversal list below.

\set ON_ERROR_STOP on

BEGIN;

-- Cutoff: only sessions that already existed before the P1-2 deploy. Replace with the deploy
-- timestamp recorded in the results document. This is what keeps the backfill off any session the
-- agent is writing right now.
\set cutoff '2026-08-11T00:00:00Z'

-- ---------------------------------------------------------------- reversal list (capture FIRST)
CREATE TEMP TABLE p1_2_backfilled AS
SELECT s.id
FROM conversation.call_sessions s
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz;

-- ---------------------------------------------------------------- before
SELECT 'before' AS phase, coalesce(final_disposition, 'NULL') AS disposition, count(*)
FROM conversation.call_sessions GROUP BY 1, 2 ORDER BY 2;

-- ---------------------------------------------------------------- 1. escalated (provable)
UPDATE conversation.call_sessions s
SET final_disposition = 'escalated'
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz
  AND EXISTS (SELECT 1 FROM conversation.escalation_cases e WHERE e.session_id = s.id);

-- ---------------------------------------------------------------- 2. abandoned (provable)
-- Runs second so an escalated session is never relabelled, matching _derive_disposition's own
-- precedence: escalation outranks everything.
UPDATE conversation.call_sessions s
SET final_disposition = 'abandoned'
WHERE s.final_disposition IS NULL
  AND s.created_at < :'cutoff'::timestamptz
  AND NOT EXISTS (
        SELECT 1 FROM conversation.turns t
        WHERE t.session_id = s.id AND t.speaker = 'caller');

-- ---------------------------------------------------------------- after
SELECT 'after' AS phase, coalesce(final_disposition, 'NULL') AS disposition, count(*)
FROM conversation.call_sessions GROUP BY 1, 2 ORDER BY 2;

-- Reversal list: save this output. It is the exact set to reset if the backfill must be undone.
SELECT 'reversal_id' AS kind, id FROM p1_2_backfilled ORDER BY id;

-- Safety assertion: nothing outside the CHECK vocabulary can have been written.
SELECT 'ILLEGAL VALUE PRESENT' AS alarm, final_disposition, count(*)
FROM conversation.call_sessions
WHERE final_disposition IS NOT NULL
  AND final_disposition NOT IN ('resolved', 'escalated', 'dropped', 'abandoned')
GROUP BY 2;

-- ROLLBACK for the dry run. Change to COMMIT only after reviewing the before/after counts.
ROLLBACK;
```

### 18.4 How to run it — dry run first, always

```bash
# 1. Dry run: the script ends in ROLLBACK, so this changes nothing.
docker exec -i docker-compose-postgres-1 psql -U telecom -d telecom \
  < scripts/backfill_p1_2_dispositions.sql | tee /tmp/p1_2_backfill_dryrun.txt
```

Read the before/after blocks. Sanity checks before going further:

- `escalated` should land near **58** — that is the escalation-case count. A wildly different number
  means the join is wrong; **STOP**.
- `escalated + abandoned + remaining NULL` must equal the original NULL count exactly.
- The `ILLEGAL VALUE PRESENT` query must return **zero rows**.
- Save the reversal list.

Only then flip the final `ROLLBACK;` to `COMMIT;` and re-run. **Commit the file with `ROLLBACK;`
restored**, so a future reader who runs it blindly cannot mutate anything.

### 18.5 Ordering — this runs LAST

Run the backfill **after** §9.2's rebuild and after the §9.3 probe rows have been deleted. Two reasons:
the cutoff must be a real deploy timestamp, and probe rows must not be swept into a historical
backfill. Slot it as step 13.5 in §10, immediately before writing the completion report.

### 18.6 Reversal

```sql
UPDATE conversation.call_sessions
SET final_disposition = NULL
WHERE id IN ( <the reversal list from 18.4> );
```

Exact, because the list is captured before any UPDATE runs. No guesswork, no time-window heuristics.

### 18.7 What to expect afterwards

`kpis()` will report an escalation rate over the full history and a resolution rate near zero — and
**that is correct**, not a bug. The escalations are real and now visible; resolutions genuinely were
never recorded and are not recoverable. The resolution rate becomes meaningful only for calls placed
after the P1-2 deploy. State that plainly next to any figure you report, and record the deploy
timestamp beside it (§3.9).

The `/sessions?disposition=escalated` filter becomes useful immediately, across all history. That is
the functional win that changed my recommendation.

### 18.8 Additions to the §15 completion report

12. The `git grep` output from gate 17.2, and confirmation of zero hits in build/deploy/CI paths.
13. The 17.5 `X-Role` grep — the definitive proof that no client sends it any more.
14. The full before/after disposition counts from the 18.4 dry run **and** from the committed run.
15. The reversal list, or its row count plus where you stored it.
16. Confirmation that the committed script still ends in `ROLLBACK;`.
