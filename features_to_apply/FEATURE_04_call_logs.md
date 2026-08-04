# Feature 4 — Call History & Transcripts (`/calls`)

> **Cookbook 4 of the admin-dashboard integration series.**
> Target branch: local `version_80` (HEAD `eda5f58`). Source of truth: `chouaib-saad/livekit_agent` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`.
> Builds on the applied substrate of Feature 0 (integration), Feature 1 (advisors), Feature 2 (availability), Feature 3 (callbacks).

---

## 0. Read this first — what makes Feature 4 different

Features 1, 2 and 3 were pure wiring jobs: the backend already exposed everything the page needed, and the work was to stop lying with mock data. **Feature 4 is the first feature where the backend does not have an endpoint for the main thing the page does.**

There is exactly one session endpoint in the whole API:

```python
@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: DbSession, role: ConseillerRole) -> dict:
```

You can fetch **one call if you already know its UUID**. There is no way to discover a UUID. The `/calls` page is a list-then-drill-down page. Without a list endpoint it cannot exist.

This falls squarely inside your rule 3(c): *"missing endpoints that expose existing backend functionality/data to the frontend… You are creating access, not new features."* Every field the new endpoint returns is already persisted in `conversation.call_sessions` and `crm.customers`. **No business logic is invented, no existing function is touched.** The additive surface is:

- **one new method** appended to `SupervisionRepository` (`session_list`) — existing methods untouched, **zero new imports** (see §3.1),
- **one new route** in `main.py` (`GET /api/v1/sessions`) — inserted directly above the existing detail route.

The second thing that makes this feature different: **the mock page invents more data than any page so far.** `calls.tsx` renders an AI-generated summary, keyword chips, a waveform, a "Play recording" button, per-turn clock timestamps and per-turn entity chips. **Four of those six have no backing data anywhere in the system.** §8 lists them individually. They are flagged, not built.

---

## 1. Feature name & scope

**Feature:** Call History & Transcripts — the supervision record of every voice session: who called, when, how long, how it ended, and the full masked transcript with the sentiment timeline.

### In scope

| Capability | Backing data | Status |
|---|---|---|
| Paginated list of call sessions, newest first | `conversation.call_sessions` | **new endpoint** (§3) |
| Customer identity per row (name, VIP, language, MSISDN) | `crm.customers` join | **new endpoint** (§3) |
| Filter by disposition | `final_disposition` | **new endpoint** |
| Search by phone number | `call_sessions.msisdn` | **new endpoint** |
| Duration, start/end instants, turn count | existing columns | **new endpoint** |
| Full masked transcript, speaker- and agent-attributed | `GET /sessions/{id}` → `turns[]` | existing, reused |
| Sentiment timeline joined to turns | `GET /sessions/{id}` → `sentiment[]` | existing, reused |
| Disposition + max frustration on the detail header | `GET /sessions/{id}` | existing, reused |
| Deep-linkable selection (`/calls?session=<uuid>`) | — | frontend |

### Explicitly out of scope (and why)

| Not built | Reason |
|---|---|
| AI-generated call summary | **No summary column exists in any model.** §8.1 |
| Keyword chips | **No keywords column exists.** §8.1 |
| Total tokens used | **No token accounting exists anywhere in the platform.** §8.2 |
| Waveform + "Play recording" | `audio_record_url` exists but there is no streaming/signed-URL endpoint, and no waveform data. §8.3 |
| Per-turn wall-clock timestamps | `Turn.created_at` exists but `session_detail` does not return it, and that endpoint is frozen by rule 2. §8.4 |
| Per-turn entity chips | `Turn` has no entities column. Replaced with the **real** `detected_intent` / `detected_language`. §5.6 |
| Policy verdict trail per call | `/api/v1/policy/verdicts?session_id=` exists and would slot in cleanly — deferred to the Guardrails cookbook. §8.5 |
| Escalation dossier per call | `/api/v1/escalations` exists — deferred to the Decisions/action-ledger cookbook. §8.5 |
| Chat conversations | `/conversations` is a separate route with a separate mock. Not this feature. |

### Route status — zero navigation churn

`/calls` **already exists** in `nav.ts` (section `PLATFORM`, shortcut already assigned) and already has an entry in `routeTree.gen.ts`. As in Feature 3:

> **`routeTree.gen.ts` must show an empty diff after this patch.** No nav entry, no `PAGE_META` entry, no shortcut. If the generated tree changes, something regenerated wrongly — investigate before committing.

Adding `validateSearch` to an existing file route does **not** alter the generated tree. Confirmed against the Feature 2 diff behaviour.

---

## 2. Backend reference (exact names & paths)

### 2.1 `apps/business-api/src/business_api/repositories.py` (`0f9acd1f`)

Module docstring: *"Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."*

The only session-related method:

```python
    def session_detail(self, session_id: str) -> dict | None:
        sid = to_uuid(session_id)
        call = self._s.get(CallSession, sid) if sid else None
        if call is None:
            return None
        turns = self._s.scalars(select(Turn).where(Turn.session_id == sid).order_by(Turn.turn_index)).all()
        sentiment = self._s.scalars(
            select(SentimentSample).where(SentimentSample.session_id == sid).order_by(SentimentSample.turn_index)
        ).all()
        return {
            "session_id": str(call.id),
            "disposition": call.final_disposition,
            "duration_seconds": call.duration_seconds,
            "max_frustration": float(call.max_frustration_score),
            "turns": [
                {"index": t.turn_index, "speaker": t.speaker, "agent": t.active_agent, "text": t.transcript_masked}
                for t in turns
            ],
            "sentiment": [{"index": x.turn_index, "score": float(x.score), "label": x.label} for x in sentiment],
        }
```

**Read that return dict carefully. It contains no customer, no MSISDN, no timestamps, no channel, no recording, no summary, no keywords.** Five keys total. Everything the page shows in its header must therefore come from the list row, not the detail — this drives the whole data-flow design in §5.2.

Already imported at module top and reusable by the new method: `func`, `select`, `Session`, `CallSession`, `Turn`, `SentimentSample`, `Customer`, `Subscription`, `to_uuid`.

### 2.2 `apps/business-api/src/business_api/main.py` (`ff52daff`)

Verbatim, the two routes that bracket the insertion point:

```python
@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Masked transcript + sentiment timeline + disposition for a call session."""
    data = SupervisionRepository(session).session_detail(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data
```

Role aliases (verbatim):

```python
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]
```

### 2.3 `packages/persistence/src/persistence/models/conversation.py` (`ec4592ad`)

Module docstring: *"Written by the agent-worker through a NON-BLOCKING async writer (never on the voice path). Turns / sentiment_samples are append-only."*

`CallSession` → `conversation.call_sessions`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `customer_id` | FK → `crm.customers` | **nullable** — anonymous callers exist |
| `subscription_id` | FK | nullable |
| `msisdn` | `String(20)` | the calling number, **raw** |
| `channel` | `voice \| chat`, default `'voice'` | |
| `livekit_room` | text | |
| `start_time` / `end_time` | timestamptz | **nullable** |
| `duration_seconds` | int | **nullable** |
| `final_disposition` | `resolved \| escalated \| dropped \| abandoned` | **nullable while in flight** |
| `max_frustration_score` | `Numeric(5,2)` | **nullable — see F2, this is a live 500** |
| `recording_consent` | bool | |
| `audio_record_url` | text | nullable |
| `created_at` | timestamptz | |

`Turn` → `conversation.turns`: `session_id`, `turn_index`, `speaker` (`caller \| agent`), `active_agent String(40)`, `detected_language` (`fr \| ar \| en`), `transcript_masked Text`, `detected_intent String(80)`, `created_at`. **`UniqueConstraint(session_id, turn_index, speaker)`** — see F5.

`SentimentSample` → `conversation.sentiment_samples`: `session_id`, `turn_index`, `score Numeric(5,2)`, `label` (`positive \| neutral \| negative \| angry`).

### 2.4 `packages/persistence/src/persistence/models/crm.py` (`65fe123c`)

`Customer` carries `UUIDPrimaryKey, Timestamps, **SoftDelete**`. Fields used here: `first_name`, `last_name`, `vip_flag`, `preferred_language`, `contact_number`, `status`.

**`SoftDelete` matters:** a deleted customer's row still exists, so the join still resolves a name. But `session_detail`'s sibling `customer_360` does not filter soft-deleted rows either, so we match existing platform behaviour and do not filter. Consistency over cleverness. Noted in §8.6.

---

## 3. Endpoints

### 3.0 Contract table (authoritative)

| Method | Path | Min role | Status |
|---|---|---|---|
| `GET` | `/api/v1/sessions` | **`superviseur`** | **NEW** — §3.1, §3.2 |
| `GET` | `/api/v1/sessions/{session_id}` | `conseiller` | existing, unchanged |

**Why `superviseur` for the list.** Every other *browse-the-whole-platform* read is `superviseur`: `/escalations`, `/actions`, `/kpis`, `/system/overview`, `/telemetry/timeline`, `/advisors`, `/advisors/coverage`. The `conseiller` reads are all *single-record, need-to-know* (`customers/{id}/360`, `sessions/{id}`, `advisors/on-call`). A list of every call anyone ever made is a supervision surface, so it takes the supervision rank.

Recall from `security.py` that `require_role` is a **minimum-rank** gate (`conseiller` 1 < `superviseur` 2 < `administrateur` 3), so the dashboard's `administrateur` session passes both. **Still declare the exact contract role on each server function** — Feature 2 decision #1. Do not collapse them to one role because "admin passes anyway".

### 3.1 New repository method — `session_list`

**File:** `apps/business-api/src/business_api/repositories.py`
**Placement:** immediately **after** the existing `session_detail` method and **before** `escalations`. Do not modify a single line of any existing method.

```python
    def session_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        disposition: str | None = None,
        customer_id: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Paginated index of call sessions for the supervision dashboard.

        Read-only, like every method here. Exposes columns that are already persisted; it
        computes nothing the platform does not already know.
        """
        stmt = select(CallSession)
        count_stmt = select(func.count()).select_from(CallSession)

        if disposition:
            stmt = stmt.where(CallSession.final_disposition == disposition)
            count_stmt = count_stmt.where(CallSession.final_disposition == disposition)

        cid = to_uuid(customer_id) if customer_id else None
        if cid is not None:
            stmt = stmt.where(CallSession.customer_id == cid)
            count_stmt = count_stmt.where(CallSession.customer_id == cid)

        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(CallSession.msisdn.ilike(like))
            count_stmt = count_stmt.where(CallSession.msisdn.ilike(like))

        total = self._s.scalar(count_stmt) or 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        # start_time is nullable on in-flight rows; fall back to created_at so ordering is total.
        ordering = func.coalesce(CallSession.start_time, CallSession.created_at).desc()
        rows = self._s.scalars(stmt.order_by(ordering).limit(limit).offset(offset)).all()

        customer_ids = {r.customer_id for r in rows if r.customer_id}
        customers = {}
        if customer_ids:
            customers = {
                c.id: c
                for c in self._s.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
            }

        turn_counts: dict = {}
        if rows:
            turn_counts = dict(
                self._s.execute(
                    select(Turn.session_id, func.count())
                    .where(Turn.session_id.in_([r.id for r in rows]))
                    .group_by(Turn.session_id)
                ).all()
            )

        items = []
        for r in rows:
            customer = customers.get(r.customer_id)
            items.append({
                "session_id": str(r.id),
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "customer_name": f"{customer.first_name} {customer.last_name}".strip() if customer else None,
                "customer_vip": bool(customer.vip_flag) if customer else False,
                "preferred_language": customer.preferred_language if customer else None,
                "msisdn": r.msisdn,
                "channel": r.channel,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration_seconds": r.duration_seconds,
                "disposition": r.final_disposition,
                "max_frustration": (
                    float(r.max_frustration_score) if r.max_frustration_score is not None else None
                ),
                "recording_consent": bool(r.recording_consent),
                "has_recording": bool(r.audio_record_url),
                "turn_count": int(turn_counts.get(r.id, 0)),
            })

        return {"sessions": items, "total": total, "limit": limit, "offset": offset}
```

**Notes that are not optional:**

- **Zero new imports.** `func`, `select`, `CallSession`, `Turn`, `Customer`, `to_uuid` are all already imported at the top of the file. Verify with `git diff` that the import block is untouched.
- **Two `IN` lookups, not N+1.** Same hydration shape as `callbacks._hydrate`. Follows the house pattern.
- **`limit` is clamped to 200** server-side. A caller cannot ask for the whole table.
- **`max_frustration` is null-guarded here**, deliberately unlike the existing `session_detail`. See F2 — I am not fixing the existing method, but I am not copying its bug into new code either.
- **`audio_record_url` is never returned**, only the boolean `has_recording`. Leaking a storage URL to the browser when there is no signed-URL flow would be a quiet security regression. §8.3.
- Ruff: line-length 110, `from __future__ import annotations` already at file top. The code above conforms.

### 3.2 New route

**File:** `apps/business-api/src/business_api/main.py`
**Placement:** insert **immediately above** `@app.get("/api/v1/sessions/{session_id}")`, after the `customer_360` route.

```python
@app.get("/api/v1/sessions")
def session_index(session: DbSession, role: SuperviseurRole, limit: int = 50, offset: int = 0,
                  disposition: str | None = None, customer_id: str | None = None,
                  search: str | None = None) -> dict:
    """Paginated index of call sessions (supervision list view).

    The detail endpoint below answers "what happened on this call"; this one answers
    "which calls exist", which is otherwise undiscoverable from outside the database.
    """
    return SupervisionRepository(session).session_index_payload(
        limit=limit, offset=offset, disposition=disposition,
        customer_id=customer_id, search=search,
    )
```

> **Stop. Two naming traps in the four lines above — fix both before you paste.**
>
> 1. The function is named `session_index`, **not** `session_list`. `main.py` already binds the module-level name `session_detail`; a second def named `session_list` would not collide today, but the repository method is called `session_list` and the route is imported into the same mental namespace during review. Distinct names, no ambiguity.
> 2. **The body above calls `session_index_payload`, which does not exist.** The method defined in §3.1 is `session_list`. Change the call to `SupervisionRepository(session).session_list(...)`. This is deliberate — the previous three patches each surfaced exactly one place where a guide's stated call shape did not match the real implementation (Feature 2 §4 decision #1, `requireRole`). Verify the callee name against §3.1 rather than trusting this snippet.

Corrected body:

```python
    return SupervisionRepository(session).session_list(
        limit=limit, offset=offset, disposition=disposition,
        customer_id=customer_id, search=search,
    )
```

**No routing-order hazard.** The `/advisors/coverage` comment in `main.py` warns that a literal segment must be declared before `{advisor_id}`. That hazard does not apply here: `/api/v1/sessions` and `/api/v1/sessions/{session_id}` differ in **segment count**, so Starlette cannot confuse them. Declaring the list first is stylistic consistency, not a requirement.

**No CORS change.** The dashboard reaches the backend through the TanStack server proxy (Feature 0 decision). The browser never issues a cross-origin request to `:8108`. `CORS_ORIGINS` stays untouched.

### 3.3 Response shapes

`GET /api/v1/sessions?limit=50&offset=0` →

```json
{
  "sessions": [
    {
      "session_id": "3f1c…",
      "customer_id": "9ab2…",
      "customer_name": "Karim Haddad",
      "customer_vip": false,
      "preferred_language": "ar",
      "msisdn": "+21620123456",
      "channel": "voice",
      "start_time": "2026-08-02T13:04:11+00:00",
      "end_time": "2026-08-02T13:08:23+00:00",
      "duration_seconds": 252,
      "disposition": "resolved",
      "max_frustration": 2.5,
      "recording_consent": true,
      "has_recording": false,
      "turn_count": 14
    }
  ],
  "total": 137,
  "limit": 50,
  "offset": 0
}
```

`GET /api/v1/sessions/{id}` → exactly the five keys in §2.1. Nothing more will appear, no matter what the mock implies.

---

## 4. Findings that drive the design (F1–F14)

### F1 — There is no list endpoint, and nothing else can substitute
`telemetry_timeline()` returns the last 50 sessions but projects them to `{timestamp: "%H:%M:%S", duration, frustration, disposition}` — **no id**, so you cannot navigate from it. `system_overview()` returns only a count. Neither is a list. The additive endpoint is unavoidable, which is why §3 exists.

### F2 — `session_detail` 500s on any call with a NULL frustration score ⚠️

```python
"max_frustration": float(call.max_frustration_score),
```

`max_frustration_score` is `Numeric(5,2)` and nullable. `float(None)` raises `TypeError`, which FastAPI turns into an unhandled **500**, not a clean error. Any call session written before a sentiment sample lands — **including every call still in flight** — makes the detail pane explode.

**This is a real pre-existing backend bug and it will be the first thing your testers hit.** But rule 2 says backend business logic is locked, and this is inside an existing method. So:

- **I am not fixing it in this patch.** It is flagged in §8.7 with the one-line fix, awaiting your go-ahead.
- **The frontend must survive it.** The detail pane treats a 500 as a first-class state with an honest message ("This call's record could not be loaded") and a Retry, and the **list stays fully usable** — you can still browse and select other calls. That is the difference between a bad row and a broken page.

The new list endpoint does **not** share the bug: §3.1 null-guards the same field.

### F3 — The timezone rule matches Feature 3, and inverts Feature 2
Neither the list nor the detail payload contains a business-local string. `start_time`/`end_time` are bare UTC instants (`isoformat()`). So, exactly as in Feature 3 — and **opposite** to Feature 2's *render `local` verbatim* invariant — we **must** convert, and must convert into the **business** zone, not the browser's.

**Reuse `formatBusinessTime` from `src/lib/nexus/callback-view.ts` (Feature 3). Do not write a second copy.** Two formatters drifting apart is precisely the failure this rule exists to prevent. If a call log and a callback queue disagree about what "09:00" means, the dashboard is worse than useless.

The business zone comes from `getCoverage({ days: 1 }).timezone`, the pattern established and shipped in Feature 3. The list page already needs no other coverage data, so the query is cheap and — critically — **already cached** by TanStack Query if the operator visited `/availability` or `/callbacks` first. Fallback behaviour is unchanged: if coverage fails, render UTC **with a visible caption saying so**, never silently.

### F4 — Transcripts are already PII-masked; do not mask them again
`Turn.transcript_masked` is written by the pii-shield package on the way in. **Do not run `maskPhone` or any other scrubber over transcript text** — you would corrupt already-safe content and hide real evidence from supervisors. Masking is applied to **`msisdn` only**, which is stored raw, matching the mock's existing `maskPhone(c.phone)` treatment and the Feature 3 decision on `customer_phone`.

### F5 — Two turns legitimately share the same index → `key={index}` is a bug
`UniqueConstraint(session_id, turn_index, speaker)` means `(0, caller)` and `(0, agent)` can both exist. `session_detail` orders by `turn_index` alone, so those two rows arrive adjacent in unspecified relative order.

- React keys **must** be `` `${index}-${speaker}` ``. Using the index alone produces duplicate keys, and React will silently reuse DOM nodes across renders — which in a transcript means **attributing one speaker's words to the other**. This is the single highest-consequence detail in the feature.
- The sentiment join is keyed by `turn_index` only, so a sample maps to *both* rows at that index. Attach sentiment to the **`caller`** row only — the samples measure caller frustration, and painting the agent's line "angry" would be a fabrication. Documented in §5.6.

### F6 — Sentiment is sparse and independently ordered
`sentiment[]` is a separate array with its own indices; there is no guarantee of one sample per turn. Build a `Map<number, SentimentSample>` and treat a miss as "no reading" — render nothing, not a neutral zero. A missing measurement is not a calm caller.

### F7 — `status.ts` has no `dropped` and no `abandoned` → blank cells
Dispositions are `resolved | escalated | dropped | abandoned`, plus **`null`** while a call is in flight. The canonical truth table has `resolved` and `escalated` but neither `dropped` nor `abandoned`, and `StatusChip` does `if (!def) return null`.

This is the **third consecutive feature** to hit this defect class (Feature 1's advisor statuses, Feature 3's callback statuses). Same remedy: a **total** mapping in the view layer, never a raw pass-through.

| `final_disposition` | `status.ts` key | Rationale |
|---|---|---|
| `resolved` | `resolved` | exact match (disc / low / soft) |
| `escalated` | `escalated` | exact match (triangle / critical / inverted) |
| `dropped` | `failed` | triangle / critical / outline — the call broke |
| `abandoned` | `closed` | square / inert / flat — the caller left; not a system failure |
| `null` | `in_progress` | half / medium / soft — still live |
| anything else | `in_progress` + raw text in `title` | never blank |

`dropped` and `abandoned` are genuinely different events and the table keeps them visually distinct. **Zero new tokens, zero `status.ts` edits.**

### F8 — `formatDuration` already exists and already does the right thing
`src/lib/nexus/format.ts` exports `formatDuration(seconds)` → `"04:12"`. Reuse it. `duration_seconds` is nullable → render `"—"`. Do not write a second duration formatter.

### F9 — Pagination must be built in from the start
Feature 3 inherited a hard `limit=100` with no offset and could only *warn* about truncation. Here **we author the endpoint**, so it takes `limit` + `offset` + `total` from day one and the UI gets a real "Load more". This is the one place in the series where we are not apologising for a backend constraint.

### F10 — `customer_id` is nullable; anonymous calls are normal
An inbound call from an unrecognised MSISDN has no customer row. `customer_name` is `null`. Render the **MSISDN as the primary identifier** and `Unknown caller` as the secondary label — never `"null null"`, never an empty avatar. `initials()` must not be called with a null name.

### F11 — `channel` can be `chat`
Default is `'voice'`, but the column permits `chat`, and `/conversations` is a separate page. **`/calls` does not filter by channel** — the endpoint returns everything, because silently hiding rows from a supervision log is worse than showing a labelled chat row. Non-voice rows get a `Token` reading the channel. Flagged in §8.8 in case you want a voice-only filter.

### F12 — Selection belongs in the URL
The mock holds selection in `useState`, so a supervisor cannot send a colleague a link to a specific call — the single most obvious thing anyone will want to do with this page. Selection moves to a validated search param, `/calls?session=<uuid>`. Refresh, back-button and deep links all work. This costs one `validateSearch` and changes no generated file.

### F13 — `turn_count` prevents a lie in the list
Without it, every row looks identical in weight. A 40-turn call and a 2-turn call are very different supervision objects. It is one grouped `COUNT`, already batched in §3.1.

### F14 — The E2E harness must not snapshot with `CREATE TABLE … AS SELECT` + `DROP`
Restated because it destroyed real data during Feature 1 and was only discovered during Feature 2: the harness that snapshotted `routing.advisor_shifts` that way **permanently lost the original grid**. `conversation.turns` is append-only and is the least recoverable table in this system.

**Binding rule for this feature's harness:** read-only verification against seeded data, or `pg_dump` to a file before touching anything. **Never** `CREATE TABLE tmp AS SELECT` followed by `DROP TABLE`. Feature 4 needs **no** DB mutation at all to be tested — every endpoint here is a read.

---

## 5. Frontend implementation plan

### 5.1 File manifest

| File | Action |
|---|---|
| `src/lib/api/sessions.server.ts` | **new** — 2 server functions |
| `src/lib/nexus/call-view.ts` | **new** — pure helpers |
| `src/components/nexus/transcript.tsx` | **new** — transcript + sentiment rendering |
| `src/lib/nexus/query-keys.ts` | **modified** — append standalone `callKeys` |
| `src/lib/nexus/data.ts` | **modified** — remove call mocks (§5.7, guarded) |
| `src/routes/calls.tsx` | **rewritten** |
| `src/routeTree.gen.ts` | **must not change** |
| `nav.ts`, `status.ts`, `primitives.tsx`, `modal.tsx`, `format.ts` | **untouched** |

Zero new npm dependencies. Zero new design tokens. Zero mutations — **this feature is entirely read-only**, so the Feature 2 POST-transport rule never comes up.

### 5.2 Data flow

```
/calls?session=<uuid>
  │
  ├─ useQuery callKeys.list(filters)   → listSessions()      → GET /api/v1/sessions
  │     └─ rows carry identity, timing, disposition, turn_count
  │
  ├─ useQuery availabilityKeys.coverage(1) → getCoverage()   → business timezone (F3, cached)
  │
  └─ useQuery callKeys.detail(id)      → getSessionDetail()  → GET /api/v1/sessions/{id}
        enabled: Boolean(sessionId)       └─ turns + sentiment ONLY
```

**The header of the detail pane is rendered from the list row, not the detail response** — because the detail response has no customer, no MSISDN and no timestamps (§2.1). The selected row is found in the already-fetched list. Consequence, and it must be handled: **a deep link to a session that is not on the current page has no row**, so the header falls back to an id-only presentation while the transcript still loads. Covered in §7 scenario 14.

### 5.3 `src/lib/api/sessions.server.ts`

> **Copy the exact middleware composition from the proven `src/lib/api/availability.server.ts`.** Feature 2 proved that a guide-stated `requireRole(...)` shape can diverge from the implementation. `requireRole` is a **factory** — `requireRole("superviseur")` returns the middleware. Open the shipped file and mirror it rather than trusting the snippet below.

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type CallSessionRow = {
  session_id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  preferred_language: string | null;
  msisdn: string | null;
  channel: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
  disposition: string | null;
  max_frustration: number | null;
  recording_consent: boolean;
  has_recording: boolean;
  turn_count: number;
};

export type SessionIndex = {
  sessions: CallSessionRow[];
  total: number;
  limit: number;
  offset: number;
};

export type TranscriptTurnRow = {
  index: number;
  speaker: string;
  agent: string | null;
  text: string | null;
};

export type SentimentRow = {
  index: number;
  score: number;
  label: string;
};

export type SessionDetail = {
  session_id: string;
  disposition: string | null;
  duration_seconds: number | null;
  max_frustration: number | null;
  turns: TranscriptTurnRow[];
  sentiment: SentimentRow[];
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  disposition: z.string().trim().max(40).optional(),
  search: z.string().trim().max(40).optional(),
});

const DetailInput = z.object({
  sessionId: z.string().uuid(),
});

export const listSessions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data }) =>
    businessApi<SessionIndex>("/api/v1/sessions", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.disposition ? { disposition: data.disposition } : {}),
        ...(data.search ? { search: data.search } : {}),
      },
      role: "superviseur",
    }),
  );

export const getSessionDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => DetailInput.parse(data))
  .handler(async ({ data }) =>
    businessApi<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(data.sessionId)}`, {
      method: "GET",
      role: "conseiller",
    }),
  );
```

**Three deliberate choices:**

1. **Empty filters are omitted from `query`, not sent empty.** Feature 3 flagged the risk that `businessApi` might strip or forward empty values inconsistently; here `?disposition=` would filter for the empty string and return nothing. Omission is unambiguous.
2. **`z.string().uuid()` on the detail input.** `to_uuid` returns `None` for garbage, which becomes a 404 — but validating client-side turns a hand-edited URL into an instant, honest error instead of a round-trip.
3. **`max_frustration` is typed `number | null`** even though the *existing* detail endpoint can never return null (it crashes first, F2). If §8.7 is approved, the type is already correct and no frontend change is needed.

### 5.4 `src/lib/nexus/call-view.ts`

```ts
import { formatBusinessTime } from "@/lib/nexus/callback-view";
import { formatDuration } from "@/lib/nexus/format";
import type { CallSessionRow, SentimentRow, TranscriptTurnRow } from "@/lib/api/sessions.server";

/** F7 — total mapping onto the canonical status truth table. Never returns undefined. */
export function dispositionKey(disposition: string | null): string {
  switch (disposition) {
    case "resolved":
      return "resolved";
    case "escalated":
      return "escalated";
    case "dropped":
      return "failed";
    case "abandoned":
      return "closed";
    default:
      return "in_progress";
  }
}

/** Human label, preserving the raw backend word even when it maps onto another chip. */
export function dispositionLabel(disposition: string | null): string {
  if (!disposition) return "In progress";
  return disposition.charAt(0).toUpperCase() + disposition.slice(1);
}

/** F5 — index alone is NOT unique; speaker disambiguates caller/agent at the same index. */
export function turnKey(turn: TranscriptTurnRow): string {
  return `${turn.index}-${turn.speaker}`;
}

/** F6 — sparse by design; a miss means "not measured", not "neutral". */
export function sentimentByIndex(samples: SentimentRow[]): Map<number, SentimentRow> {
  const map = new Map<number, SentimentRow>();
  for (const sample of samples) map.set(sample.index, sample);
  return map;
}

/** Existing achromatic tokens only. No new colours, no hex. */
export function sentimentTone(label: string | null): string {
  switch (label) {
    case "angry":
      return "bg-n-11";
    case "negative":
      return "bg-n-9";
    case "positive":
      return "bg-n-7";
    default:
      return "bg-surface-3";
  }
}

export function durationLabel(seconds: number | null): string {
  return seconds === null || seconds === undefined ? "—" : formatDuration(seconds);
}

/** F3 — no local string in this payload, so we convert into the BUSINESS zone. */
export function callTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone);
}

/** F10 — anonymous callers are normal. Never render "null null". */
export function callerName(row: CallSessionRow): string {
  return row.customer_name?.trim() || "Unknown caller";
}

export function frustrationLabel(score: number | null): string {
  return score === null || score === undefined ? "—" : score.toFixed(1);
}
```

**Note the absence of a search helper.** Unlike `advisorMatches` / `callbackMatches`, filtering here is **server-side** (F9) — the client holds one page, so a client-side filter would filter only that page and quietly mislead. Search input is debounced into the query key instead.

### 5.5 `src/lib/nexus/query-keys.ts`

Append a standalone export, mirroring `availabilityKeys` (Feature 2) and `callbackKeys` (Feature 3). Do not restructure the existing `queryKeys` object.

```ts
export const callKeys = {
  all: ["calls"] as const,
  list: (search: string, disposition: string, limit: number) =>
    ["calls", "list", search, disposition, limit] as const,
  detail: (sessionId: string) => ["calls", "detail", sessionId] as const,
};
```

`limit` is in the key because "Load more" grows the page size (§5.8) — omitting it would serve a stale short page from cache.

### 5.6 `src/components/nexus/transcript.tsx`

Renders the turn list. Real data replaces every invented element of the mock:

| Mock element | Replacement | Source |
|---|---|---|
| `turn.at` clock | `#{index}` in `t-mono-s text-ink-5` | `turn_index` (F13/§8.4) |
| `turn.speaker` | same, but `caller` / `agent` from the DB | `Turn.speaker` |
| — *(new)* | active agent name in a `Token` | `Turn.active_agent` |
| `turn.entities[]` chips | sentiment label + score on caller turns | `SentimentSample` (F5) |

```tsx
import { Token } from "@/components/nexus/primitives";
import { sentimentByIndex, sentimentTone, turnKey } from "@/lib/nexus/call-view";
import type { SentimentRow, TranscriptTurnRow } from "@/lib/api/sessions.server";
import { cn } from "@/lib/utils";

export function Transcript({
  turns,
  sentiment,
}: {
  turns: TranscriptTurnRow[];
  sentiment: SentimentRow[];
}) {
  const byIndex = sentimentByIndex(sentiment);

  return (
    <ul>
      {turns.map((turn) => {
        const isCaller = turn.speaker === "caller";
        // F5 — sentiment measures the CALLER. Never paint the agent's line with it.
        const mood = isCaller ? byIndex.get(turn.index) : undefined;

        return (
          <li key={turnKey(turn)} className="border-t border-stroke-subtle px-sp-7 py-sp-6">
            <div className="flex flex-wrap items-center gap-sp-4">
              <span className="t-mono-s text-ink-5">#{turn.index}</span>
              <span className="t-micro text-ink-4">{isCaller ? "Caller" : "Agent"}</span>
              {turn.agent ? <Token mono={false}>{turn.agent}</Token> : null}
              {mood ? (
                <span className="flex items-center gap-sp-3">
                  <span
                    aria-hidden="true"
                    className={cn("block size-[6px] rounded-[1px]", sentimentTone(mood.label))}
                  />
                  <span className="t-caption text-ink-4">
                    {mood.label} · {mood.score.toFixed(1)}
                  </span>
                </span>
              ) : null}
            </div>
            {/* F4 — transcript_masked is ALREADY PII-masked. Do not scrub it again. */}
            <p className={cn("t-body mt-sp-3", isCaller ? "text-ink-2" : "text-ink-3")}>
              {turn.text?.trim() || <span className="text-ink-5">(no transcript captured)</span>}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
```

Caller and agent are separated by **ink level** (`text-ink-2` vs `text-ink-3`), not by colour, bubbles or alignment — consistent with the monochrome bible and with how every other list in the console distinguishes weight.

### 5.7 `src/lib/nexus/data.ts` — guarded mock removal

Feature 1 removed `ADVISORS`, Feature 3 removed `CALLBACKS`. Feature 4 targets `CALLS`, `CallRow`, `CALL_SUMMARY`, `CALL_KEYWORDS`, `TRANSCRIPT`, `TranscriptTurn`, `WAVEFORM`.

> **Do not delete blindly.** Run this first:
>
> ```bash
> grep -rn "CALL_SUMMARY\|CALL_KEYWORDS\|WAVEFORM\|TRANSCRIPT\|CallRow\|TranscriptTurn\|\bCALLS\b" src/
> ```
>
> `overview.tsx`, `analytics.tsx` and `conversations.tsx` are still mock-driven and may import some of these. **Remove only the symbols whose sole importer was `calls.tsx`.** Anything still referenced elsewhere stays until that page is wired. A broken build in an untouched route is a self-inflicted wound.

### 5.8 `src/routes/calls.tsx` (rewritten)

Layout is preserved exactly: `PageSection` with `grid gap-sp-6 xl:grid-cols-[340px_1fr]`, a `Card padded={false}` master list with `max-h-[720px] overflow-y-auto`, and a detail column of stacked `Card`s. Same spacing tokens, same type tokens, same `Avatar` sizes. A reviewer should recognise the page instantly.

```tsx
import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PhoneOff } from "lucide-react";
import { z } from "zod";
import {
  Avatar,
  Button,
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, Shimmer } from "@/components/nexus/states";
import { Transcript } from "@/components/nexus/transcript";
import { getCoverage } from "@/lib/api/availability.server";
import { getSessionDetail, listSessions } from "@/lib/api/sessions.server";
import {
  callTime,
  callerName,
  dispositionKey,
  dispositionLabel,
  durationLabel,
  frustrationLabel,
} from "@/lib/nexus/call-view";
import { availabilityKeys, callKeys } from "@/lib/nexus/query-keys";
import { initials, maskPhone } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

const SCOPES = [
  { id: "", label: "All" },
  { id: "resolved", label: "Resolved" },
  { id: "escalated", label: "Escalated" },
  { id: "dropped", label: "Dropped" },
  { id: "abandoned", label: "Abandoned" },
];

export const Route = createFileRoute("/calls")({
  // F12 — deep-linkable selection. Does NOT alter routeTree.gen.ts.
  validateSearch: z.object({ session: z.string().uuid().optional() }),
  head: () => ({
    meta: [
      { title: "Call History & Transcripts — Nexus" },
      {
        name: "description",
        content: "End-of-call records, sentiment timelines and full transcripts for every session.",
      },
      { property: "og:title", content: "Call History & Transcripts — Nexus" },
      { property: "og:description", content: "Transcripts and outcomes for customer calls." },
    ],
  }),
  component: CallsPage,
});

function CallsPage() {
  const navigate = useNavigate({ from: "/calls" });
  const { session: selected } = Route.useSearch();

  const [search, setSearch] = useState("");
  const [disposition, setDisposition] = useState("");
  const [limit, setLimit] = useState(50);

  const listQuery = useQuery({
    queryKey: callKeys.list(search, disposition, limit),
    queryFn: () => listSessions({ data: { limit, offset: 0, disposition: disposition || undefined, search: search || undefined } }),
  });

  // F3 — business timezone; shared cache with /availability and /callbacks.
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const detailQuery = useQuery({
    queryKey: callKeys.detail(selected ?? ""),
    queryFn: () => getSessionDetail({ data: { sessionId: selected! } }),
    enabled: Boolean(selected),
  });

  const rows = listQuery.data?.sessions ?? [];
  const total = listQuery.data?.total ?? 0;
  const activeRow = rows.find((r) => r.session_id === selected) ?? null;

  const select = (sessionId: string) =>
    navigate({ search: { session: sessionId }, replace: true });

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[340px_1fr]">
      {/* ---------------- Master list ---------------- */}
      <Card padded={false} className="overflow-hidden">
        <div className="space-y-sp-5 border-b border-stroke-subtle p-sp-6">
          <SearchInput
            placeholder="Search by number"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Segmented items={SCOPES} active={disposition} onSelect={setDisposition} />
        </div>

        {listQuery.isPending ? (
          <div className="space-y-sp-4 p-sp-6">
            <Shimmer className="h-[52px]" />
            <Shimmer className="h-[52px]" />
            <Shimmer className="h-[52px]" />
          </div>
        ) : listQuery.isError ? (
          <div className="p-sp-6">
            <ErrorState error={listQuery.error} onRetry={() => listQuery.refetch()} />
          </div>
        ) : rows.length === 0 ? (
          <div className="p-sp-6">
            <EmptyState
              icon={PhoneOff}
              title="No calls found"
              description="No session matches this filter yet."
            />
          </div>
        ) : (
          <>
            <ul className="max-h-[720px] overflow-y-auto">
              {rows.map((row) => {
                const active = row.session_id === selected;
                const name = callerName(row);
                return (
                  <li key={row.session_id}>
                    <button
                      type="button"
                      onClick={() => select(row.session_id)}
                      className={cn(
                        "flex w-full items-start gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5 text-left transition-colors duration-[120ms]",
                        active ? "bg-surface-3" : "hover:bg-surface-3/60",
                      )}
                    >
                      <Avatar initials={initials(name)} name={name} />
                      <span className="min-w-0 flex-1">
                        <span className="t-ui block truncate text-ink-1">{name}</span>
                        <span className="t-mono-s block truncate text-ink-4">
                          {row.msisdn ? maskPhone(row.msisdn) : "No number"}
                        </span>
                      </span>
                      <span className="text-right">
                        <span className="t-mono-s block text-ink-3">
                          {durationLabel(row.duration_seconds)}
                        </span>
                        <span className="t-caption block text-ink-5">
                          {callTime(row.start_time, timeZone)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="flex items-center justify-between gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-5">
              <span className="t-caption text-ink-5">
                Showing {rows.length} of {total}
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </div>
          </>
        )}
      </Card>

      {/* ---------------- Detail ---------------- */}
      <div className="space-y-sp-6">
        {!selected ? (
          <Card>
            <EmptyState
              icon={PhoneOff}
              title="Select a call"
              description="Pick a session on the left to read its transcript."
            />
          </Card>
        ) : (
          <>
            <Card>
              <div className="flex flex-wrap items-start gap-sp-6">
                <Avatar
                  initials={initials(activeRow ? callerName(activeRow) : "?")}
                  name={activeRow ? callerName(activeRow) : undefined}
                  size="xl"
                />
                <div className="min-w-0">
                  <h2 className="t-title-2 text-ink-1">
                    {activeRow ? callerName(activeRow) : "Call record"}
                  </h2>
                  <p className="t-mono-s mt-sp-2 text-ink-4">
                    {selected.slice(0, 8)}
                    {activeRow?.msisdn ? ` · ${maskPhone(activeRow.msisdn)}` : ""}
                  </p>
                  <div className="mt-sp-5 flex flex-wrap items-center gap-sp-4">
                    <StatusChip
                      status={dispositionKey(
                        detailQuery.data?.disposition ?? activeRow?.disposition ?? null,
                      )}
                    />
                    <Token>
                      {durationLabel(
                        detailQuery.data?.duration_seconds ?? activeRow?.duration_seconds ?? null,
                      )}
                    </Token>
                    {activeRow ? <Token>{callTime(activeRow.start_time, timeZone)}</Token> : null}
                    {activeRow?.customer_vip ? <Token strong>VIP</Token> : null}
                    {activeRow?.channel && activeRow.channel !== "voice" ? (
                      <Token mono={false}>{activeRow.channel}</Token>
                    ) : null}
                  </div>
                </div>
                <div className="ml-auto text-right">
                  <span className="t-micro block text-ink-5">Peak frustration</span>
                  <span className="t-metric-m block text-ink-1">
                    {frustrationLabel(detailQuery.data?.max_frustration ?? null)}
                  </span>
                </div>
              </div>

              {!timeZone && !coverageQuery.isPending ? (
                <p className="t-caption mt-sp-5 text-ink-5">
                  Times shown in UTC — the business timezone could not be loaded.
                </p>
              ) : null}
            </Card>

            <Card padded={false}>
              <div className="flex items-center justify-between gap-sp-5 p-sp-7">
                <CardHeader
                  title="Transcript"
                  subtitle="Speaker-attributed and PII-masked at capture."
                />
                {detailQuery.data ? (
                  <span className="t-caption text-ink-5">
                    {detailQuery.data.turns.length} turns
                  </span>
                ) : null}
              </div>

              {detailQuery.isPending ? (
                <div className="p-sp-7">
                  <CardSkeleton />
                </div>
              ) : detailQuery.isError ? (
                <div className="p-sp-7">
                  {/* F2 — a NULL frustration score makes the backend 500. Stay honest, stay usable. */}
                  <ErrorState
                    error={detailQuery.error}
                    onRetry={() => detailQuery.refetch()}
                  />
                </div>
              ) : detailQuery.data && detailQuery.data.turns.length === 0 ? (
                <div className="p-sp-7">
                  <EmptyState
                    icon={PhoneOff}
                    title="No transcript"
                    description="This session ended before any turn was recorded."
                  />
                </div>
              ) : detailQuery.data ? (
                <Transcript
                  turns={detailQuery.data.turns}
                  sentiment={detailQuery.data.sentiment}
                />
              ) : null}
            </Card>
          </>
        )}
      </div>
    </PageSection>
  );
}
```

**Call-site adaptations to verify against the shipped components** (call-site only — never edit the primitives):

- `SearchInput` in the template takes `{ placeholder, className }`. If it does not forward `value`/`onChange`, **do not change the component** — wrap a local `<input>` with the identical classes, or add the props only if `git log` shows Feature 0/1 already extended it. Check before writing.
- `Segmented` items use `{ id, label }` and `onSelect`. Confirmed `type="button"` since Feature 1 — safe inside any form.
- `EmptyState` icon usage must mirror the exact call shape in the shipped `advisors.tsx` (component reference, not element).
- `Shimmer` / `CardSkeleton` / `ErrorState` come from Feature 0's `states.tsx`; `ErrorState` takes `{ error, onRetry }` and `errorMessage` already handles plain strings (Feature 1 fix).
- **No `Modal` here** — this feature opens no overlay, so the `PageSection` `.rise` transform trap does not apply. If you later add one, it **must** portal to `document.body`.

---

## 6. Design-system compliance

| Rule | How it is met |
|---|---|
| No new colours | Only `bg-n-11 / bg-n-9 / bg-n-7 / bg-surface-3` and `text-ink-*`, all pre-existing |
| No new type styles | `t-ui`, `t-mono-s`, `t-caption`, `t-micro`, `t-body`, `t-title-2`, `t-metric-m` |
| No new spacing | `sp-3 … sp-7`, `gap-sp-*` as used across the console |
| No new components | `Avatar`, `Button`, `Card`, `CardHeader`, `EmptyState`, `SearchInput`, `Segmented`, `StatusChip`, `Token` |
| No new status keys | F7 total mapping onto existing `status.ts` entries |
| No arbitrary values | `size-[6px]` matches the mock's existing `size-[4px]` idiom; grid/height literals copied verbatim from the mock |
| Achromatic | Every tone is an `n-*` token; grep proves no `#hex` / `rgb(` |

---

## 7. Validation checklist

### 7.1 Static

- [ ] `bun --bun tsc --noEmit` → exit 0.
- [ ] `bun --bun run lint` → **exactly the 36-problem baseline** (28 pre-existing prettier + 8 warnings). No new problems.
- [ ] `bun --bun run build` → exit 0 (pre-existing `inputValidator` deprecation notices only).
- [ ] `git diff --stat src/routeTree.gen.ts` → **empty**.
- [ ] `git diff` on backend → **only** `repositories.py` (+1 method) and `main.py` (+1 route). Import blocks unchanged in both.
- [ ] `git status` → the 2 pre-existing agent-worker files still the only other backend changes.
- [ ] `package.json` / `bun.lock` unchanged.
- [ ] `grep -rn "rgb(\|#[0-9a-fA-F]\{3,6\}" src/lib/nexus/call-view.ts src/components/nexus/transcript.tsx src/routes/calls.tsx` → no hits.
- [ ] `grep -n "getDay(\|toLocaleString(\|getHours(" ` on the three new files → no hits (all time formatting goes through `formatBusinessTime`).
- [ ] `grep -rn "maskPhone" src/components/nexus/transcript.tsx` → **no hits** (F4).
- [ ] `status.ts`, `primitives.tsx`, `modal.tsx`, `format.ts`, `nav.ts` → untouched.
- [ ] `ruff check apps/business-api` → clean, line-length 110.

### 7.2 Pure helper tests

- [ ] `dispositionKey` for all six inputs (`resolved`, `escalated`, `dropped`, `abandoned`, `null`, `"weird"`) returns a key that **exists in `status.ts`** — assert against the real table, not a copy.
- [ ] `turnKey` returns distinct values for `{index:0,speaker:"caller"}` and `{index:0,speaker:"agent"}` (F5).
- [ ] `sentimentByIndex` on a sparse array → misses return `undefined`, not a zero sample.
- [ ] `durationLabel(null)` → `"—"`; `durationLabel(252)` → `"04:12"`.
- [ ] `callerName` on `{customer_name:null}` → `"Unknown caller"`; on `{customer_name:"  "}` → `"Unknown caller"`.
- [ ] `callTime(null, "Africa/Tunis")` → `"—"`; `callTime("garbage", tz)` → `"—"`.
- [ ] `callTime` output is **identical** under `TZ=America/New_York` and `TZ=Africa/Tunis` (business-zone invariance, the Feature 2/3 proof repeated).
- [ ] `frustrationLabel(null)` → `"—"`; `frustrationLabel(2.5)` → `"2.5"`.

### 7.3 Backend contract

- [ ] `GET /api/v1/sessions` with `X-Role: conseiller` → **403** (`requires role >= superviseur`).
- [ ] Same with `X-Role: superviseur` → 200; with `administrateur` → 200 (minimum-rank).
- [ ] `?limit=999` → response `limit` clamped to **200**.
- [ ] `?limit=0` / `?limit=-5` → clamped to 1, no crash.
- [ ] `?offset` beyond `total` → `sessions: []`, `total` still correct.
- [ ] `?disposition=escalated` → every row escalated; `total` reflects the **filtered** count, not the table count.
- [ ] `?search=<partial msisdn>` → case-insensitive partial match; `?search=zzzz` → empty list, `total: 0`.
- [ ] `?customer_id=<garbage>` → treated as no filter (matches `to_uuid` returning `None`), no 500.
- [ ] Ordering: newest first, and a row with `start_time IS NULL` still appears (ordered by `created_at`).
- [ ] `turn_count` matches `SELECT count(*) FROM conversation.turns WHERE session_id = …` for three sampled rows.
- [ ] A session whose customer is soft-deleted still resolves a name (§8.6).
- [ ] `GET /api/v1/sessions/{unknown-uuid}` → 404 `"session not found"`.
- [ ] **F2 probe (read-only):** find a row with `max_frustration_score IS NULL`; `GET /sessions/{id}` → confirm **500**. Record it. Do not fix without §8.7 approval.

### 7.4 Live E2E (browser, full Docker stack)

- [ ] Unauthenticated `/calls` → redirect to `/login`; after login → `/calls` renders.
- [ ] Sidebar `/calls` entry and its existing `PAGE_META` subtitle are unchanged.
- [ ] List renders real rows; the count line reads `Showing N of M`.
- [ ] Selecting a row pushes `?session=<uuid>` into the URL; **browser Back** returns to the previous selection.
- [ ] **Full page reload on `/calls?session=<uuid>`** restores the same call.
- [ ] Deep link to a **valid uuid not on the current page**: transcript loads, header falls back to id-only, no crash (§5.2).
- [ ] Deep link to a **malformed** `?session=abc` → validated away cleanly, no unhandled error.
- [ ] Scope `Segmented` through all five values; each refetches and `total` changes.
- [ ] Search a partial number → list narrows; clearing restores.
- [ ] `Load more` grows the page; the button disappears once `rows.length === total`.
- [ ] Transcript: caller and agent turns at the **same index** both render, correct text attributed to each (F5 — the regression that duplicate keys would cause).
- [ ] Sentiment appears **only** on caller turns; turns without a sample show no dot.
- [ ] A session with **zero turns** → "No transcript" empty state, not a blank card.
- [ ] A session with NULL duration/disposition → `—` and the `In progress` chip; **no blank chip anywhere** (F7).
- [ ] An anonymous call (no customer) → `Unknown caller` + masked MSISDN, avatar renders.
- [ ] A `chat`-channel row → labelled `Token`, still listed (F11).
- [ ] The F2 row (NULL frustration) → detail pane shows the error state with Retry; **the list remains fully usable and other calls still open**.
- [ ] Timezone: with the container/OS at `America/New_York`, displayed call times are **identical** to `Africa/Tunis`.
- [ ] Stop the coverage source only → the UTC caption appears; times still render.
- [ ] `docker stop docker-compose-business-api-1` → "Could not reach the service" + "Try again" on **both** list and detail; restart → recovery without reload.
- [ ] **Zero direct browser requests to `:8108`** (all traffic through the proxy).
- [ ] `/availability` and `/callbacks` still render (shared `availabilityKeys.coverage(1)` cache is read-only here).
- [ ] Any other page that imported the removed mocks still builds (§5.7 grep).

> **Harness rule (F14): this entire checklist is read-only. Do not create, drop or truncate any table.** If you need fixtures, insert rows through the normal seed path and delete them by primary key, or snapshot with `pg_dump` first. The Feature 1 harness permanently destroyed `advisor_shifts` with `CREATE TABLE … AS SELECT` + `DROP`; `conversation.turns` is append-only and would be even less recoverable.

---

## 8. Ambiguities & decisions needing your confirmation

### 8.1 AI summary and keywords do not exist — the mock's two biggest cards
The mock renders an "AI-Generated Summary" card (`CALL_SUMMARY`, subtitle *"Produced at end of call."*) and a keyword chip row (`CALL_KEYWORDS`). **There is no summary column, no keywords column, and no summarisation job anywhere in the platform.** Your Phase 3 feature list explicitly names "summary, keywords" as expected, so this is a genuine gap between the template's promise and the system.

By rule 3 this is business logic, so I have not built it. **This patch simply omits both cards.** Options, for your call:
1. Leave them out (current plan) — the sentiment timeline is real and carries similar signal.
2. Add `summary` / `keywords` columns to `call_sessions` and have the agent-worker write them at end of call. **Real new feature — needs its own spec and your explicit approval.**
3. Generate a summary on demand in the dashboard. I would advise against it: unpinned, unaudited, non-reproducible, and it would sit inside a supervision record that is otherwise a faithful log.

### 8.2 "Total tokens used" does not exist
Your feature list names it. **No model, service or table in the repository records token usage** — not `call_sessions`, not `turns`, not the audit ledger. It cannot be exposed because it is not captured. Requires instrumentation in the agent-worker (out of this phase's scope). Confirm you are content to drop it from `/calls`.

### 8.3 Recording playback — data exists, access path does not
`CallSession.audio_record_url` and `recording_consent` are real columns. But there is no endpoint serving audio, no signed-URL issuer, and the object-storage package is not wired into business-api. The mock's "Play recording" button and 64-bar waveform have no backing data (`WAVEFORM` is a literal array).

**Decision: omitted, and `audio_record_url` is deliberately not returned by the new endpoint** (§3.1) — exposing a raw storage URL to a browser with no signed-URL flow would be a quiet security regression, and it is not needed to render anything.

If you want playback, the additive shape would be `GET /api/v1/sessions/{id}/recording` returning a short-lived signed URL, gated on `recording_consent` being true. That is arguably rule-3(c) access-creation rather than a new feature, but it touches storage credentials, so I want your explicit go-ahead. Waveform rendering would additionally require peak data that nothing computes.

### 8.4 Per-turn timestamps are one frozen line away
`Turn.created_at` exists in the model. `session_detail` simply does not project it. Adding `"at": t.created_at.isoformat() if t.created_at else None` to that dict comprehension is one line and would give real per-turn clock times instead of `#index`.

But it is a modification to an existing method, and rule 2 locks existing backend logic. **I have not touched it.** Say the word and it becomes a one-line diff. (Note: since `turns` is append-only and written by an async writer off the voice path, `created_at` reflects **write** time, not exact utterance time — it may lag the real audio by the writer's queue delay. `turn_index` is the authoritative ordering either way, which is part of why I am comfortable shipping `#index`.)

### 8.5 Two adjacent supervision surfaces already exist for this session
`GET /api/v1/policy/verdicts?session_id=` (superviseur) and `GET /api/v1/escalations` (superviseur, carries `session_id` + `dossier`) would both slot naturally into this page as extra tabs — "why did the agent refuse that" and "what happened when it escalated" are the two questions a supervisor asks immediately after reading a transcript.

I kept them out to hold the one-feature-one-cookbook line, and because both are the core of the **Guardrails** and **Decisions/action-ledger** cookbooks. **Confirm you want them cross-linked from `/calls` later**, and I will design them as tabs on this page rather than standalone routes.

### 8.6 Soft-deleted customers still resolve a name
`Customer` carries `SoftDelete`. The new list method does not filter deleted customers, so a purged customer's historical calls still show their name. This **matches** `customer_360`, which does not filter either. It is consistent, and arguably correct for an audit log — but it interacts with the retention job (`POST /api/v1/jobs/retention`). If your retention policy requires anonymising historical call rows, tell me and I will add the filter (rendering `Unknown caller` for deleted customers).

### 8.7 ⚠️ Recommended one-line backend bug fix — needs approval
`repositories.py`, in the existing `session_detail`:

```python
"max_frustration": float(call.max_frustration_score),
```

→

```python
"max_frustration": float(call.max_frustration_score) if call.max_frustration_score is not None else None,
```

This is a **modification to existing backend code**, which your rule 2 forbids without approval, so **I have not included it in the patch**. But it is a live 500 on any in-flight or unsampled call, it will be hit within minutes of using the page, and it affects the voice agent's own supervision reads too — not just this dashboard. The frontend handles it gracefully (§7.4), so this is not blocking; it is simply the highest-value one-line change available in the repository right now. **Approve and I will fold it in.**

### 8.8 Should `/calls` hide `chat` sessions?
Current decision: **no** — a supervision log that silently drops rows is dangerous, so chat rows appear with a channel `Token`. But `/conversations` exists as a separate destination, so you may prefer `/calls` to mean voice only. One `where` clause either way. Your call.

### 8.9 Search covers MSISDN only
Searching by **customer name** would need a join and an `ilike` across `first_name`/`last_name`, which is easy to add to the new method — but names are the one field most likely to be governed by the PII policy that already masks transcripts, and I did not want to introduce a name-search surface without asking. Confirm if you want it.

---

## 9. Summary of the diff

**Backend (additive only, 2 files):**
- `apps/business-api/src/business_api/repositories.py` — `+1` method `session_list`, zero new imports, no existing line changed.
- `apps/business-api/src/business_api/main.py` — `+1` route `GET /api/v1/sessions` (`superviseur`), inserted above the existing detail route.

**Frontend (`Frontend/admin_dashboard/` only):**
- **new** `src/lib/api/sessions.server.ts`, `src/lib/nexus/call-view.ts`, `src/components/nexus/transcript.tsx`
- **modified** `src/lib/nexus/query-keys.ts` (append `callKeys`), `src/lib/nexus/data.ts` (guarded mock removal)
- **rewritten** `src/routes/calls.tsx`
- **unchanged** `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx`, `modal.tsx`, `format.ts`

**Zero** new npm dependencies · **zero** new design tokens · **zero** new status keys · **zero** mutations · **zero** CORS changes · **zero** navigation changes.

---

## 10. Next feature

**Tickets (`/tickets`).** Expect the hardest gap analysis so far: ticketing is reached through the **`ticketing-glpi` MCP server on :8202**, and `business-api` exposes ticket data only as a nested array inside `customer_360`. There is no `/api/v1/tickets` list route and no ticket detail route. `crm.Customer.glpi_user_id` and `Ticket.glpi_ticket_id` are the join keys. That cookbook will have to decide — with you — whether business-api gains a thin read-through to GLPI or whether the admin ticket view is scoped down to what the platform already persists.
