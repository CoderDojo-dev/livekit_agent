# Feature 1 — Advisors Registry (Members Management)

**Cookbook 1 of the admin-dashboard integration series.**

| | |
|---|---|
| Source of truth | `chouaib-saad/livekit_agent` @ `version_79`, SHA `eda5f58ff3f468755db455e445eb6117b6909b5c` |
| Depends on | Feature 0 — Integration Substrate (applied, 12/12 live) |
| Backend files modified | **ZERO** |
| Backend files created | **ZERO** |
| New backend endpoints | **ZERO** |
| CORS / middleware changes | **NONE** (already present, and moot under the proxy transport) |
| New npm dependencies | **ZERO** |
| New design tokens | **ZERO** |
| Frontend files created | 4 |
| Frontend files modified | 2 |

This is the first feature cookbook and deliberately the first one: `routing.advisors` is the
foreign key for `advisor_shifts`, `advisor_time_off`, callback claims and escalation routing.
Every later cookbook (Availability, Callbacks, Escalations) resolves an advisor id that this
feature is responsible for putting on screen.

---

## 0. Prerequisite contract (verify before applying)

This cookbook consumes six symbols delivered by Feature 0. The patch report confirms all of them
exist, but the report did not include signatures. **Check these six lines first**; if any differs,
the adaptation is mechanical and noted inline where it is used.

| Symbol | File | Signature this cookbook assumes |
|---|---|---|
| `businessApi` | `src/lib/api/business-api.ts` | `businessApi<T>(path: string, opts?: { method?, query?, body?, role? }): Promise<T>` |
| `authedMiddleware` | `src/lib/api/middleware.ts` | server-fn middleware; provides `context.session` |
| `requireRole` | `src/lib/api/middleware.ts` | `requireRole(minimum: BackendRole)` → middleware |
| `AdminSession` / `BackendRole` | `src/lib/api/session.ts` | `{ sub, role, exp }`, `"conseiller" \| "superviseur" \| "administrateur"` |
| `TableSkeleton` | `src/components/nexus/states.tsx` | `{ rows: number; cols: number }` |
| `TableErrorRow` | `src/components/nexus/states.tsx` | `{ colSpan: number; message: string; onRetry?: () => void }` |

**If `context.session` is not what `authedMiddleware` provides** (e.g. it is `context.user`),
change the four `context.session.role` references in file **A** only. Nothing else touches it.

**Cosmetic note on Feature 0, not blocking.** The patch report says `business-api.ts` sets
`mode: "cors"` on its `fetch`. Under the proxy transport that call executes in Nitro, not a
browser, where `mode` is inert — it is ignored, not harmful. Leave it or drop it; it changes no
behaviour. I mention it only so it is not later mistaken for evidence of a direct-from-browser call.

---

## 1. Feature name & scope

**Advisors registry — the list of human advisors an escalation can reach, and full CRUD over it.**

### In scope

- List advisors, including the inactive ones, with a live/inactive toggle.
- Create an advisor.
- Edit an advisor (contact details, skills, language, capacity, status, rota flag).
- Deactivate / reactivate an advisor (`is_active`).
- Delete an advisor permanently, with an interstitial that states the real consequences.
- Client-side filtering of the loaded list by name, email, phone and skill.
- Loading, empty, error and mutation-error states.

### Explicitly out of scope (each has a reason, not an omission)

| Excluded | Why |
|---|---|
| Weekly shift grid, time-off | Feature 2. Endpoints exist (`/schedule`, `/time-off`) but are a distinct screen with its own data model. |
| Coverage report | Feature 2. `/api/v1/advisors/coverage` is a supervision view over shifts, not over the registry. |
| Claim / release | Not an admin action. `POST /advisors/claim` and `/{id}/release` are `conseiller`-scoped calls made **by the voice agent** during an escalation. Exposing a "claim" button in the admin UI would let an operator silently consume live routing capacity. Deliberately not surfaced. |
| "Handled today" volume | **No such data exists in the backend.** See §5.3 — flagged, not invented. |

---

## 2. Backend reference

### 2.1 Files (read in full, verbatim, at the pinned SHA)

| Path | SHA | Role |
|---|---|---|
| `apps/business-api/src/business_api/advisors.py` | `bd0c9803` | Registry operations + the atomic claim |
| `apps/business-api/src/business_api/main.py` | `ff52daff` | Route declarations, `AdvisorPayload`, RBAC wiring |
| `apps/business-api/src/business_api/security.py` | `a059de0d` | `require_role`, rank ladder |
| `packages/persistence/src/persistence/models/routing.py` | `307c5a68` | `Advisor` ORM model + CHECK constraints |

### 2.2 The `Advisor` model — the authoritative field list

From `routing.py`, table `routing.advisors` (inherits `UUIDPrimaryKey`, `Timestamps`):

| Column | Type | Null | Server default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | generated | |
| `full_name` | `String(120)` | **no** | — | the only truly required field |
| `email` | `String(255)` | yes | — | |
| `phone_e164` | `String(20)` | yes | — | one of phone/SIP is required *by service logic* |
| `sip_uri` | `String(255)` | yes | — | |
| `skills` | `String(200)` | no | `'general'` | **comma-joined string in the DB, list in the API** |
| `language` | `String(10)` | no | `'fr'` | |
| `status` | `String(20)` | no | `'offline'` | CHECK `IN ('available','busy','offline')` |
| `max_concurrent_calls` | `Integer` | no | `1` | CHECK `> 0` |
| `active_calls` | `Integer` | no | `0` | CHECK `>= 0` — **machine-owned** |
| `is_on_call` | `Boolean` | no | `false` | escalation-rota flag, *not* a presence state |
| `is_active` | `Boolean` | no | `true` | soft-delete / employment flag |

Three constraints are enforced at the database level and will surface as a **500**, not a 400, if
the UI ever sends a violating value, because `main.py` only catches `ValueError`/`KeyError`:
`status` outside the three literals, `max_concurrent_calls <= 0`, `active_calls < 0`.
**The UI must therefore make these three states unreachable by construction** — see §5.5.

### 2.3 The serializer — the exact JSON shape

`advisors.to_dict()` is the single serializer used by list, create, update, claim and on-call.
Every advisor payload anywhere in the API has exactly these twelve keys:

```python
{
    "id": str(advisor.id),
    "full_name": advisor.full_name,
    "email": advisor.email,
    "phone_e164": advisor.phone_e164,
    "sip_uri": advisor.sip_uri,
    "skills": [s for s in (advisor.skills or "").split(",") if s],
    "language": advisor.language,
    "status": advisor.status,
    "max_concurrent_calls": advisor.max_concurrent_calls,
    "active_calls": advisor.active_calls,
    "is_on_call": advisor.is_on_call,
    "is_active": advisor.is_active,
}
```

Note what is **absent**: no `created_at`/`updated_at` (they exist on the row via `Timestamps` but
are not serialized), no team, no seniority, no per-advisor call counters. The API surface is
narrower than the table, and the table is narrower than the UI template. §5.3 resolves that.

### 2.4 Service-layer rules that the UI must respect

**Reachability (`create_advisor`, `update_advisor`)**

```python
if not data.get("phone_e164") and not data.get("sip_uri"):
    raise ValueError("an advisor needs a phone_e164 or a sip_uri to be reachable")
```

On update this is checked **after** the mutation is applied to the ORM object, so clearing the last
reachable destination raises. `main.py` maps `ValueError` → **400** with the message as `detail`.
The UI mirrors this check client-side *and* surfaces the server message — mirroring alone is not
enough, because a concurrent edit could remove the other destination between load and save.

**`exclude_none=True` on both create and update.** `main.py` calls
`payload.model_dump(exclude_none=True)`. Consequence, and it is a sharp one:

> **`null` cannot clear a field.** Sending `{"email": null}` drops the key entirely and the old
> email is kept. To clear an optional text field the UI must send an **empty string**.

`update_advisor` loops `for field in (...): if field in data and data[field] is not None` — an
empty string passes both tests and is written. This is why every text input in the form submits
`""` rather than `undefined`. Getting this wrong produces a form that silently refuses to clear
fields, which is exactly the class of bug that looks like a frontend bug for a week.

**Skills normalisation.** `create` does `",".join(data.get("skills") or ["general"])`;
`update` does `",".join(data["skills"]) or "general"`. So an empty skills list falls back to
`general` on both paths. `_skills()` lower-cases and strips on read, but **`create`/`update` store
the raw strings**. Two advisors can therefore hold `"Billing"` and `"billing"`; matching still
works (it lower-cases at claim time) but the table would show inconsistent casing. The form
normalises to lower-case on submit — a display decision, justified in §5.4, that cannot change
matching behaviour because matching already lower-cases.

**`active_calls` is machine-owned.** It is incremented by `claim_advisor` under
`FOR UPDATE SKIP LOCKED` and decremented by `release_advisor`. `AdvisorPayload` has no
`active_calls` field, so it is not writable through the API at all. The UI renders it read-only.

**`status` is partly machine-owned.** `claim_advisor` flips `available → busy` when the advisor
reaches capacity; `release_advisor` flips `busy → available` when it drops below. An admin can
still set `status` through PATCH. Both are legitimate, so the field is editable — but the form
labels it as live presence, and §8.2 raises the one honest ambiguity this creates.

**Delete is a hard delete.** `session.delete(advisor)`. Both `advisor_shifts.advisor_id` and
`advisor_time_off.advisor_id` declare `ondelete="CASCADE"`, so **the weekly grid and every
recorded absence are destroyed with the row, irreversibly.** There is no restore path and the
audit ledger is not written by this endpoint. This is why the UI leads with Deactivate and treats
Delete as the exceptional action, with an interstitial that names the cascade explicitly.

---

## 3. Endpoints

### 3.1 Existing — reused as-is. No new endpoint is created for this feature.

All paths are on `business-api`, `:8108`. "Min role" is enforced by
`require_role` reading the `X-Role` header (injected server-side by the Feature 0 proxy).

#### `GET /api/v1/advisors` — min role `superviseur`

Query: `include_inactive: bool = False`.

```jsonc
{ "advisors": [ { /* the 12 keys of §2.3 */ } ] }
```

Ordered `full_name ASC` server-side (`list_advisors`). No pagination, no server-side search, no
sort parameter — see §5.6 for why filtering is client-side and why that is correct *here*.

#### `POST /api/v1/advisors` — min role `administrateur` — **201**

Body `AdvisorPayload`, all fields optional at the schema level; `full_name` enforced in the
handler. Returns the created advisor object (not wrapped).

```jsonc
{ "full_name": "Nadia Rahman", "email": "nadia@…", "phone_e164": "+33612345678",
  "sip_uri": "", "skills": ["billing","general"], "language": "fr",
  "status": "offline", "max_concurrent_calls": 2, "is_on_call": false, "is_active": true }
```

Errors: **400** `{"detail": "full_name is required"}` · **400** `{"detail": "an advisor needs a
phone_e164 or a sip_uri to be reachable"}`.

#### `PATCH /api/v1/advisors/{advisor_id}` — min role `administrateur`

Same body type; returns the updated advisor object. **404** when the id does not resolve —
including when it is not a valid UUID, because `get_advisor` returns `None` if `to_uuid` fails.
So a malformed id is a 404, never a 500. **400** on the reachability violation.

#### `DELETE /api/v1/advisors/{advisor_id}` — min role `administrateur`

```jsonc
{ "deleted": true, "advisor_id": "…" }
```

**404** when unknown.

### 3.2 Not created, and why

No endpoint is added by this cookbook. Constraint 3 allows additive endpoints only to *expose
existing functionality*; the registry is already fully exposed. Three things a richer UI would
want do **not** exist and are **not** invented here — they are flagged in §8:
server-side search, pagination, and per-advisor handled-volume.

### 3.3 CORS / middleware

No change. `main.py` already installs `CORSMiddleware` with `allow_headers=["Content-Type",
"X-Role"]` and every verb this feature uses (`GET`, `POST`, `PATCH`, `DELETE`). Under the
Feature 0 proxy the browser never contacts `:8108`, so CORS never engages at all. Constraint 3(a)
is not exercised by this feature.

---

## 4. Frontend audit — what exists today

`src/routes/advisors.tsx` (`6bdd9390`) is a 100% static template: it imports `ADVISORS` from
`@/lib/nexus/data` and renders five columns.

```ts
export const ADVISORS = [
  { initials: "NR", name: "Nadia Rahman", role: "Senior",    queue: "3", handled: "184", status: "online"  },
  …
];
```

Audit against backend reality:

| Template field | Backend equivalent | Verdict |
|---|---|---|
| `initials` | — | **Derive.** `initials()` already exists in `format.ts`. |
| `name` | `full_name` | Direct map. |
| `role` ("Senior", "Team Lead") | **none** | No seniority/title column exists anywhere. Column repurposed → §5.3. |
| `queue` | **none** (`active_calls` is load, not queue depth) | Column repurposed → §5.3. |
| `handled` | **none** | **Dropped.** No source. → §5.3. |
| `status` | `status` + `is_active` | **Value domains do not match.** → §5.2. |
| — | `email`, `phone_e164`, `sip_uri`, `skills`, `language`, `max_concurrent_calls`, `is_on_call`, `is_active` | Eight real fields the template does not show. |

There are no buttons, no create path, no row actions, no loading/empty/error states — the page is
a mock. Everything in §6 is additive to a static shell.

---

## 5. Decisions

### 5.1 The one that would have silently broken the page

`StatusChip` (`primitives.tsx`) does this:

```tsx
const def = STATUS[status];
if (!def) return null;
```

And `STATUS` (`status.ts`, "the canonical status truth table. No status exists outside it.")
contains `online`, `away`, `offline`, `on_call` — but **neither `available` nor `busy`**, which are
two of the three values the backend can emit.

So the obvious wiring — `<StatusChip status={a.status} />` — renders **nothing at all** for every
available and every busy advisor. Not a fallback, not a warning: an empty cell. On a seeded dev
database where most advisors are `offline`, this can easily look like it works.

**Decision: map backend states onto existing STATUS keys in a single pure function. Do not add
keys to `STATUS`.**

Adding `available` and `busy` to `status.ts` was the alternative, and it is the one I rejected.
`status.ts` declares itself the closed truth table for the whole design system; extending it is a
design-system change, which constraint 1 forbids, and it would put two new chip definitions in
front of every other feature that reads that file. Mapping is reversible, local, and testable.

| Backend | Chip key | Chip renders | Reasoning |
|---|---|---|---|
| `is_active === false` (any status) | `inactive` | bar · inert · flat · "Inactive" | Employment state dominates presence. A deactivated advisor is never routable regardless of `status`, so showing "Online" would be a lie. Checked **first**. |
| `available` | `online` | disc · high · soft · "Online" | Reachable and under capacity. |
| `busy` | `on_call` | half · high · soft · "On call" | `busy` is set by `claim_advisor` precisely when the advisor hits `max_concurrent_calls` — they are literally on a call. |
| `offline` | `offline` | bar · inert · flat · "Offline" | Exact match. |
| anything else | `offline` | — | Unreachable through the CHECK constraint; defensive only. |

**Why `busy → on_call` and not `busy → away`.** `away` (ring · medium · outline) reads as *not
working*. `busy` means *working at capacity*. Using `away` would tell a supervisor scanning the
table that the advisor is idle-but-absent, when the truth is the opposite. The half-disc glyph of
`on_call` also carries the right visual weight: high level, soft container, same family as
`online` — a supervisor sees at a glance that both are working, which is the actual operational
question.

**The naming collision this creates, and how it is contained.** The chip key `on_call` is
unrelated to the backend boolean `is_on_call`, which is the *escalation rota* flag —
"advisors who receive the dossier when no one could take the call live" (`on_call_advisors`).
These are genuinely different concepts that unfortunately share a word. Containment rule, applied
throughout the code below:

> `is_on_call` is **never** rendered with `StatusChip`. It renders as a `Token` in its own column
> headed **Rota**. The word "On call" appears in the Status column only, and only as a
> presence state.

### 5.2 Status is a derived value, not a passthrough

Because `is_active` overrides `status`, the mapping cannot live inline in JSX — it would be
duplicated in the table, the form and any future card. It goes in one pure, client-safe module
(file **B**) that imports nothing from the server. Feature 2 will reuse it for the coverage view.

### 5.3 Column changes — the template must adapt to the backend

Constraint 4 requires an explicit, justified call here rather than a quiet reshuffle.

| Template column | Action | Justification |
|---|---|---|
| **Advisor** | Keep | `full_name`, initials derived via existing `initials()`. |
| **Role** | **Replace with Skills** | There is no role/title/seniority anywhere in `routing.advisors`. `skills` is the field that actually determines what work reaches an advisor (`claim_advisor` matches `skill_tag` against it, falling back to `general`). It occupies the same "what kind of advisor is this" slot the mock's `role` was gesturing at, and unlike `role` it is real and operationally meaningful. |
| **Queue** | **Replace with Load** | The mock's `queue` implies a per-advisor waiting queue. No such structure exists — escalations claim an advisor atomically or fall through to a callback; nothing queues on a person. `active_calls / max_concurrent_calls` is the true live number and is what the claim algorithm reads. Rendered `1/2` in `t-mono`, right-aligned, exactly as `queue` was. |
| **Handled** | **Delete the column** | **No backing data.** There is no per-advisor counter, no join, no aggregate in `advisors.py`, `repositories.py`'s advisor surface, or the KPI endpoint. Rendering `—` in every row would be worse than removing it: it implies the metric exists and is merely empty. Per constraint 3, missing *logic* is flagged, not built. See §8.1. |
| **Status** | Keep, **derived** | §5.1. |
| — | **Add Contact** | Reachability is the single most important operational fact about an advisor (a row with neither phone nor SIP cannot exist, by service rule) and it is invisible in the mock. Shows `phone_e164`, falling back to `sip_uri`, in `t-mono-s` — the treatment `Token` already uses for identifiers. |
| — | **Add Lang** | `language` gates callback slot matching (`free_slots(…, language)`), so it is not decorative. Narrow `Token`. |
| — | **Add Rota** | Surfaces `is_on_call`. Without it the flag is invisible yet decides who receives dossiers. Renders a `Token` reading `Rota` when true, and `—` when false — not a chip (§5.1). |
| — | **Add actions column** | Header intentionally empty (`<Th />`), right-aligned, `IconButton`s revealed on row hover. This is the only place in the design system where a header is blank; it is the standard convention for an affordance column and keeps `t-micro` header noise down. |

Net: 5 columns → 8. The table stays inside `TableShell` with no width overrides.

### 5.4 Skills are normalised to lower-case on submit

`_skills()` lower-cases on read, so casing never affects routing. But `create`/`update` persist raw
input, so the table would show `Billing` next to `billing`. Normalising on write makes the column
visually coherent, costs nothing behaviourally, and matches how the value is actually compared.
This is a **frontend input-normalisation choice**, not a backend behaviour change — the same string
reaches the same comparison either way.

### 5.5 Making the three CHECK constraints unreachable

`main.py` catches only `ValueError`/`KeyError`, so a constraint violation surfaces as a 500 with
no usable message. The UI removes the possibility rather than handling the error:

- `status` — a `Segmented` control over exactly `available | busy | offline`. Never free text.
- `max_concurrent_calls` — `<input type="number" min={1} step={1}>`, plus a zod `.int().min(1)`
  guard on the server function. Two independent gates.
- `active_calls` — not writable through `AdvisorPayload` at all; rendered read-only.

### 5.6 Filtering is client-side — and that is correct here, not a shortcut

`list_advisors` accepts no search parameter and returns the whole table. Adding a server-side
search endpoint would be an additive endpoint, permitted by constraint 3(c) — I rejected it
anyway. An advisor registry is a roster bounded by headcount (tens, low hundreds), the payload is
twelve scalar fields per row, and the whole list is already fetched to render the count in the
footer. Server-side search would add an endpoint, a debounce, a loading state per keystroke and a
race condition, to filter a list that is already in memory. It also filters across fields the
backend has no index for (`skills` is a comma-joined string; a server `LIKE` over it would be a
sequential scan doing worse than `Array.filter`).

The search box matches `full_name`, `email`, `phone_e164` and any skill, case-insensitively.
**If the roster ever exceeds ~1,000 rows this decision should be revisited** — recorded in §8.3.

### 5.7 A modal is required, and the design system has none

Create and edit need an overlay. The situation:

- `components/nexus/` has **no** dialog, drawer, sheet or overlay. Nineteen primitives, none modal.
- `components/ui/` has the stock shadcn `dialog`, which is styled with `bg-background`,
  `text-foreground`, `rounded-md`, `border-border` — **a different token family entirely** from
  the nexus system (`surface-*`, `ink-*`, `rounded-r-*`, `sp-*`). Dropping it in would produce a
  panel visibly not of this application: wrong radius, wrong surface, wrong type scale.
  That is precisely the design drift constraint 1 forbids.

Three options considered:

1. **Use shadcn `Dialog` as-is** — rejected: guaranteed visual drift, on the most prominent
   interaction in the feature.
2. **Re-skin shadcn `Dialog` with nexus tokens** — rejected: it means editing `components/ui/`,
   which is stock shadcn shared with the customer portal template and regenerable by the Lovable
   tooling flagged in `AGENTS.md`. A re-skin there could be reverted by a resync, and it changes a
   file outside this feature's blast radius.
3. **A nexus `Modal` shell composed strictly from existing tokens** — **chosen.**

The new `Modal` invents nothing. Its panel is `Card`'s exact class string
(`rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1`); its backdrop reuses the
topbar's established scrim treatment (`bg-surface-0/85 backdrop-blur-md` — the topbar uses
`bg-surface-0/85 backdrop-blur-md`); its header/footer bars reuse `TableShell`'s
`h-[56px] … border-b border-stroke-subtle px-sp-6` and `h-[52px] … border-t` bars verbatim. Every
value is copied from a file in this repository, not chosen. It is the same method Feature 0 used
for `TextField` (lifted from `SearchInput`), and it is reusable by Features 2, 5 and 8.

It is accessible without new dependencies: `role="dialog"`, `aria-modal`, labelled by its title,
Escape to close, backdrop click to close, focus moved to the panel on open and restored to the
trigger on close, and background scroll locked.

### 5.8 Deactivate is the primary destructive affordance; Delete is exceptional

Given the irreversible CASCADE of §2.4, the row exposes both:

- **Deactivate** (`PATCH {is_active: false}`) — reversible, keeps the shift grid and history,
  removes the advisor from `list_advisors` default view and from every routing query
  (`claim_advisor` and `on_call_advisors` both filter `is_active.is_(True)`). This is what
  "remove a member" means operationally.
- **Delete** (`DELETE`) — behind a confirmation modal that states in words that the weekly
  schedule and all recorded absences are destroyed with the row and cannot be recovered.

The confirm modal additionally **refuses to proceed while `active_calls > 0`**, explaining that
the advisor is on a live call. Rationale: deleting a claimed advisor destroys the row that
`release_advisor` will look up moments later, and release then silently 404s. I cannot fix that
race in the backend (constraint 2), so the UI declines to trigger it. This is a guard, not a
substitute for a backend fix — recorded in §8.4.

### 5.9 Mutations invalidate; they do not patch the cache

Every mutation calls `queryClient.invalidateQueries({ queryKey: advisorKeys.all })` and refetches.
Optimistic cache-patching is rejected because `status` and `active_calls` are mutated concurrently
by the voice agent's claim/release path; a patched cache would show a stale `active_calls` that
looks authoritative. A refetch costs one small request and is always truthful.

---

## 6. Implementation

### File manifest

| # | Path | Action |
|---|---|---|
| **A** | `src/lib/api/advisors.server.ts` | create — server functions + types |
| **B** | `src/lib/nexus/advisor-view.ts` | create — pure presentation mapping |
| **C** | `src/components/nexus/modal.tsx` | create — modal shell (tokens only) |
| **D** | `src/components/nexus/advisor-form.tsx` | create — create/edit form + delete confirm |
| **E** | `src/routes/advisors.tsx` | **replace** — full rewrite |
| **F** | `src/lib/nexus/data.ts` | modify — delete the `ADVISORS` export |

`ADVISORS` is imported only by `src/routes/advisors.tsx`, which file **E** rewrites. `ADVISOR_TEAM`
(a different export, used by `overview.tsx`) is **left untouched** — it belongs to the Overview
cookbook.

---

### File A — `src/lib/api/advisors.server.ts` *(new)*

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- Types: the exact shape of business_api.advisors.to_dict() ---------- */

export type AdvisorStatus = "available" | "busy" | "offline";

export type Advisor = {
  id: string;
  full_name: string;
  email: string | null;
  phone_e164: string | null;
  sip_uri: string | null;
  skills: string[];
  language: string;
  status: AdvisorStatus;
  max_concurrent_calls: number;
  active_calls: number;
  is_on_call: boolean;
  is_active: boolean;
};

/* ---------- Input schemas ----------
 * Mirrors AdvisorPayload (main.py). Empty strings are meaningful and are NOT
 * stripped: main.py uses model_dump(exclude_none=True), so null cannot clear a
 * field — only "" can. See cookbook section 2.4.
 */

const advisorFields = {
  full_name: z.string().trim().min(1, "Name is required").max(120),
  email: z.string().trim().max(255),
  phone_e164: z.string().trim().max(20),
  sip_uri: z.string().trim().max(255),
  skills: z.array(z.string().trim().min(1)).max(20),
  language: z.string().trim().min(1).max(10),
  status: z.enum(["available", "busy", "offline"]),
  max_concurrent_calls: z.number().int().min(1),
  is_on_call: z.boolean(),
  is_active: z.boolean(),
};

const CreateInput = z.object(advisorFields);
const UpdateInput = z.object({ id: z.string().min(1) }).extend(
  z.object(advisorFields).partial().shape,
);
const IdInput = z.object({ id: z.string().min(1) });
const ListInput = z.object({ includeInactive: z.boolean().default(false) });

export type AdvisorCreateInput = z.infer<typeof CreateInput>;
export type AdvisorUpdateInput = z.infer<typeof UpdateInput>;

/* ---------- Server functions ----------
 * Authorization is enforced here, in the middleware of the endpoint that
 * touches the data — not in beforeLoad. Server functions are reachable
 * independently of the route that renders them.
 *
 * NOTE: if authedMiddleware exposes the session under a different key than
 * `context.session`, the four `context.session.role` reads below are the only
 * places to change.
 */

export const listAdvisors = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    const res = await businessApi<{ advisors: Advisor[] }>("/api/v1/advisors", {
      method: "GET",
      query: { include_inactive: data.includeInactive },
      role: context.session.role,
    });
    return res.advisors;
  });

export const createAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => CreateInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Advisor>("/api/v1/advisors", {
      method: "POST",
      body: data,
      role: context.session.role,
    }),
  );

export const updateAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => UpdateInput.parse(data))
  .handler(async ({ data, context }) => {
    const { id, ...patch } = data;
    return businessApi<Advisor>(`/api/v1/advisors/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: patch,
      role: context.session.role,
    });
  });

export const deleteAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => IdInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<{ deleted: boolean; advisor_id: string }>(
      `/api/v1/advisors/${encodeURIComponent(data.id)}`,
      { method: "DELETE", role: context.session.role },
    ),
  );
```

**Why `deleteAdvisor` and `updateAdvisor` are declared `method: "POST"`.** That is the transport
of the *server function* (TanStack Start server functions are POST RPC endpoints); the HTTP verb
sent onward to `business-api` is the `method` inside `businessApi(...)`, which is `DELETE` and
`PATCH` respectively. These are two different hops. Do not "fix" the outer one.

**Why `encodeURIComponent`.** The id comes from the client. Path-segment encoding removes any
possibility of traversal or injection into the upstream path. An invalid id reaches the backend
and returns a clean 404 (§3.1), never a 500.

---

### File B — `src/lib/nexus/advisor-view.ts` *(new)*

Pure, client-safe, no server imports. This is the module that prevents the blank-status bug.

```ts
import type { Advisor, AdvisorStatus } from "@/lib/api/advisors.server";

/**
 * Map backend advisor state onto a key that exists in STATUS (status.ts).
 *
 * The backend emits available | busy | offline. STATUS contains none of the
 * first two, and StatusChip returns null for unknown keys — so passing the raw
 * value renders an empty cell. Employment state is checked first: a deactivated
 * advisor is never routable, whatever their presence flag says.
 */
export function advisorStatusKey(
  advisor: Pick<Advisor, "status" | "is_active">,
): string {
  if (!advisor.is_active) return "inactive";
  switch (advisor.status) {
    case "available":
      return "online";
    case "busy":
      return "on_call";
    case "offline":
      return "offline";
    default:
      return "offline";
  }
}

/** Labels for the status editor. Backend vocabulary, not chip vocabulary. */
export const ADVISOR_STATUS_OPTIONS: { value: AdvisorStatus; label: string }[] = [
  { value: "available", label: "Available" },
  { value: "busy", label: "Busy" },
  { value: "offline", label: "Offline" },
];

/** "1/2" — live load over configured capacity. */
export function advisorLoad(
  advisor: Pick<Advisor, "active_calls" | "max_concurrent_calls">,
): string {
  return `${advisor.active_calls}/${advisor.max_concurrent_calls}`;
}

/** Phone first, SIP as fallback. Service logic guarantees at least one exists. */
export function advisorContact(
  advisor: Pick<Advisor, "phone_e164" | "sip_uri">,
): string | null {
  return advisor.phone_e164 || advisor.sip_uri || null;
}

/** Case-insensitive match over name, email, phone and skills. */
export function advisorMatches(advisor: Advisor, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    advisor.full_name.toLowerCase().includes(q) ||
    (advisor.email ?? "").toLowerCase().includes(q) ||
    (advisor.phone_e164 ?? "").toLowerCase().includes(q) ||
    (advisor.sip_uri ?? "").toLowerCase().includes(q) ||
    advisor.skills.some((s) => s.toLowerCase().includes(q))
  );
}

/** Comma-separated input -> normalised tag list. Lower-cased: _skills() in
 *  advisors.py lower-cases before matching, so casing is never behavioural. */
export function parseSkills(input: string): string[] {
  const seen = new Set<string>();
  for (const raw of input.split(",")) {
    const tag = raw.trim().toLowerCase();
    if (tag) seen.add(tag);
  }
  return [...seen];
}
```

---

### File C — `src/components/nexus/modal.tsx` *(new)*

Every class string below is copied from an existing nexus file. Provenance is in the comments.

```tsx
import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { IconButton } from "@/components/nexus/primitives";
import { cn } from "@/lib/utils";

/**
 * Modal shell. No new tokens:
 *  - panel   = Card's class string (primitives.tsx)
 *  - scrim   = AppTopbar's scrim treatment (app-topbar.tsx)
 *  - header  = TableShell toolbar bar, h-[56px] (primitives.tsx)
 *  - footer  = TableShell footer bar, h-[52px] (primitives.tsx)
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  footer,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    restoreRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      restoreRef.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-surface-0/85 px-sp-8 py-sp-12 backdrop-blur-md"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "rise w-full max-w-[520px] overflow-hidden rounded-r-4 border border-stroke-default bg-surface-2 shadow-elev-1 outline-none",
          className,
        )}
      >
        <div className="flex min-h-[56px] items-start justify-between gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5">
          <div>
            <h2 className="t-title-3 text-ink-1">{title}</h2>
            {description ? (
              <p className="t-caption mt-sp-2 max-w-[48ch] text-ink-4">{description}</p>
            ) : null}
          </div>
          <IconButton label="Close" icon={X} onClick={onClose} />
        </div>

        <div className="px-sp-6 py-sp-6">{children}</div>

        {footer ? (
          <div className="flex h-[52px] items-center justify-end gap-sp-4 border-t border-stroke-subtle px-sp-6">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
```

---

### File D — `src/components/nexus/advisor-form.tsx` *(new)*

Uses `TextField` from Feature 0 and `Modal` from file C.

```tsx
import { useEffect, useState } from "react";
import { Button, Checkbox, Segmented, Token } from "@/components/nexus/primitives";
import { TextField } from "@/components/nexus/primitives";
import { InlineError } from "@/components/nexus/states";
import { Modal } from "@/components/nexus/modal";
import {
  ADVISOR_STATUS_OPTIONS,
  parseSkills,
} from "@/lib/nexus/advisor-view";
import type { Advisor, AdvisorStatus } from "@/lib/api/advisors.server";

export type AdvisorFormValues = {
  full_name: string;
  email: string;
  phone_e164: string;
  sip_uri: string;
  skills: string[];
  language: string;
  status: AdvisorStatus;
  max_concurrent_calls: number;
  is_on_call: boolean;
  is_active: boolean;
};

const STATUS_LABELS = ADVISOR_STATUS_OPTIONS.map((o) => o.label);

function labelToStatus(label: string): AdvisorStatus {
  return (
    ADVISOR_STATUS_OPTIONS.find((o) => o.label === label)?.value ?? "offline"
  );
}

function statusToLabel(value: AdvisorStatus): string {
  return ADVISOR_STATUS_OPTIONS.find((o) => o.value === value)?.label ?? "Offline";
}

function toFormValues(advisor: Advisor | null): AdvisorFormValues {
  return {
    full_name: advisor?.full_name ?? "",
    email: advisor?.email ?? "",
    phone_e164: advisor?.phone_e164 ?? "",
    sip_uri: advisor?.sip_uri ?? "",
    skills: advisor?.skills ?? ["general"],
    language: advisor?.language ?? "fr",
    status: advisor?.status ?? "offline",
    max_concurrent_calls: advisor?.max_concurrent_calls ?? 1,
    is_on_call: advisor?.is_on_call ?? false,
    is_active: advisor?.is_active ?? true,
  };
}

export function AdvisorFormModal({
  open,
  advisor,
  pending,
  serverError,
  onClose,
  onSubmit,
}: {
  open: boolean;
  /** null = create mode */
  advisor: Advisor | null;
  pending: boolean;
  serverError: string | null;
  onClose: () => void;
  onSubmit: (values: AdvisorFormValues) => void;
}) {
  const [values, setValues] = useState<AdvisorFormValues>(() => toFormValues(advisor));
  const [skillsText, setSkillsText] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  // Reset whenever the modal opens, or the edited advisor changes.
  useEffect(() => {
    if (!open) return;
    const next = toFormValues(advisor);
    setValues(next);
    setSkillsText(next.skills.join(", "));
    setLocalError(null);
  }, [open, advisor]);

  const isEdit = advisor !== null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLocalError(null);

    const skills = parseSkills(skillsText);
    const payload: AdvisorFormValues = { ...values, skills };

    if (!payload.full_name.trim()) {
      setLocalError("Name is required.");
      return;
    }
    // Mirrors advisors.py: an advisor needs a phone_e164 or a sip_uri.
    if (!payload.phone_e164.trim() && !payload.sip_uri.trim()) {
      setLocalError("An advisor needs a phone number or a SIP URI to be reachable.");
      return;
    }
    if (!Number.isInteger(payload.max_concurrent_calls) || payload.max_concurrent_calls < 1) {
      setLocalError("Capacity must be a whole number of 1 or more.");
      return;
    }

    onSubmit(payload);
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Edit advisor" : "New advisor"}
      description={
        isEdit
          ? "Contact details, skills and capacity. Live call count is managed by the routing engine."
          : "Register an advisor the escalation router can reach."
      }
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="advisor-form" disabled={pending}>
            {pending ? "Saving…" : isEdit ? "Save changes" : "Create advisor"}
          </Button>
        </>
      }
    >
      <form id="advisor-form" onSubmit={handleSubmit} className="flex flex-col gap-sp-6">
        <TextField
          label="Full name"
          value={values.full_name}
          onChange={(v) => setValues((s) => ({ ...s, full_name: v }))}
          placeholder="Nadia Rahman"
          autoFocus
        />

        <TextField
          label="Email"
          type="email"
          value={values.email}
          onChange={(v) => setValues((s) => ({ ...s, email: v }))}
          placeholder="nadia@example.com"
        />

        <div className="grid grid-cols-2 gap-sp-5">
          <TextField
            label="Phone (E.164)"
            value={values.phone_e164}
            onChange={(v) => setValues((s) => ({ ...s, phone_e164: v }))}
            placeholder="+33612345678"
          />
          <TextField
            label="SIP URI"
            value={values.sip_uri}
            onChange={(v) => setValues((s) => ({ ...s, sip_uri: v }))}
            placeholder="sip:nadia@pbx.local"
          />
        </div>
        <p className="t-caption -mt-sp-3 text-ink-4">
          At least one of phone or SIP is required — it is how the router reaches this advisor.
        </p>

        <TextField
          label="Skills"
          value={skillsText}
          onChange={setSkillsText}
          placeholder="general, billing, technique"
        />
        <div className="-mt-sp-3 flex flex-wrap items-center gap-sp-2">
          {parseSkills(skillsText).map((skill) => (
            <Token key={skill} mono={false}>
              {skill}
            </Token>
          ))}
          {parseSkills(skillsText).length === 0 ? (
            <span className="t-caption text-ink-4">Defaults to “general” when left empty.</span>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-sp-5">
          <TextField
            label="Language"
            value={values.language}
            onChange={(v) => setValues((s) => ({ ...s, language: v }))}
            placeholder="fr"
          />
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-3">Max concurrent calls</span>
            <input
              type="number"
              min={1}
              step={1}
              value={values.max_concurrent_calls}
              onChange={(event) =>
                setValues((s) => ({
                  ...s,
                  max_concurrent_calls: Number(event.target.value),
                }))
              }
              className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
        </div>

        <div className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Presence</span>
          <Segmented
            items={STATUS_LABELS}
            active={statusToLabel(values.status)}
            onSelect={(label) =>
              setValues((s) => ({ ...s, status: labelToStatus(label) }))
            }
          />
        </div>

        <div className="flex items-center gap-sp-5">
          <span className="flex items-center gap-sp-3">
            <Checkbox
              label="Escalation rota"
              checked={values.is_on_call}
              onChange={(checked) => setValues((s) => ({ ...s, is_on_call: checked }))}
            />
            <span className="t-ui text-ink-2">Escalation rota</span>
          </span>
          <span className="flex items-center gap-sp-3">
            <Checkbox
              label="Active"
              checked={values.is_active}
              onChange={(checked) => setValues((s) => ({ ...s, is_active: checked }))}
            />
            <span className="t-ui text-ink-2">Active</span>
          </span>
        </div>
        <p className="t-caption -mt-sp-3 text-ink-4">
          Rota advisors receive the dossier when nobody could take the call live.
        </p>

        {localError ? <InlineError message={localError} /> : null}
        {serverError ? <InlineError message={serverError} /> : null}
      </form>
    </Modal>
  );
}

export function DeleteAdvisorModal({
  advisor,
  pending,
  serverError,
  onClose,
  onConfirm,
}: {
  advisor: Advisor | null;
  pending: boolean;
  serverError: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const onLiveCall = (advisor?.active_calls ?? 0) > 0;

  return (
    <Modal
      open={advisor !== null}
      onClose={onClose}
      title="Delete advisor"
      description={advisor ? `${advisor.full_name} will be removed permanently.` : undefined}
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={onConfirm}
            disabled={pending || onLiveCall}
          >
            {pending ? "Deleting…" : "Delete permanently"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-sp-5">
        <p className="t-ui-regular text-ink-2">
          This also deletes the advisor’s weekly schedule and every recorded absence. It cannot be
          undone.
        </p>
        <p className="t-caption text-ink-4">
          To remove someone from routing while keeping their history, deactivate them instead.
        </p>
        {onLiveCall ? (
          <InlineError message="This advisor is on a live call. Wait for the call to end before deleting." />
        ) : null}
        {serverError ? <InlineError message={serverError} /> : null}
      </div>
    </Modal>
  );
}
```

> **`Checkbox` takes a `label` prop only** in the current `primitives.tsx` — it renders an
> uncontrolled input. The form above passes `checked`/`onChange`. Append these two optional props
> to `Checkbox` (three lines, no style change) or the checkboxes will not be controlled:
>
> ```tsx
> export function Checkbox({ label, checked, onChange }: {
>   label: string;
>   checked?: boolean;
>   onChange?: (checked: boolean) => void;
> }) {
>   …
>   <input
>     type="checkbox"
>     checked={checked}
>     onChange={(e) => onChange?.(e.target.checked)}
>     className="…unchanged…"
>   />
> ```
>
> The class string is untouched, so this is behavioural only — no design impact. It is listed as
> modification **G** in the validation checklist.

---

### File E — `src/routes/advisors.tsx` *(full replacement)*

```tsx
import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Power, Trash2, Users } from "lucide-react";
import {
  Avatar,
  Button,
  EmptyState,
  IconButton,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import {
  AdvisorFormModal,
  DeleteAdvisorModal,
  type AdvisorFormValues,
} from "@/components/nexus/advisor-form";
import {
  advisorContact,
  advisorLoad,
  advisorMatches,
  advisorStatusKey,
} from "@/lib/nexus/advisor-view";
import { initials } from "@/lib/nexus/format";
import {
  createAdvisor,
  deleteAdvisor,
  listAdvisors,
  updateAdvisor,
  type Advisor,
} from "@/lib/api/advisors.server";

const COLUMN_COUNT = 8;

export const advisorKeys = {
  all: ["advisors"] as const,
  list: (includeInactive: boolean) =>
    ["advisors", "list", { includeInactive }] as const,
};

export const Route = createFileRoute("/advisors")({
  head: () => ({
    meta: [
      { title: "Advisors — Nexus" },
      {
        name: "description",
        content: "Advisor registry: presence, skills, capacity and reachability.",
      },
      { property: "og:title", content: "Advisors — Nexus" },
      { property: "og:description", content: "Who is online, on call and away." },
    ],
  }),
  component: AdvisorsPage,
});

function AdvisorsPage() {
  const queryClient = useQueryClient();

  const [scope, setScope] = useState<"Active" | "All">("Active");
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Advisor | null>(null);
  const [deleting, setDeleting] = useState<Advisor | null>(null);

  const includeInactive = scope === "All";

  const advisorsQuery = useQuery({
    queryKey: advisorKeys.list(includeInactive),
    queryFn: () => listAdvisors({ data: { includeInactive } }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: advisorKeys.all });

  const createMutation = useMutation({
    mutationFn: (values: AdvisorFormValues) => createAdvisor({ data: values }),
    onSuccess: async () => {
      await invalidate();
      setFormOpen(false);
      setEditing(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: { id: string } & Partial<AdvisorFormValues>) =>
      updateAdvisor({ data: input }),
    onSuccess: async () => {
      await invalidate();
      setFormOpen(false);
      setEditing(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAdvisor({ data: { id } }),
    onSuccess: async () => {
      await invalidate();
      setDeleting(null);
    },
  });

  const advisors = advisorsQuery.data ?? [];
  const visible = useMemo(
    () => advisors.filter((advisor) => advisorMatches(advisor, search)),
    [advisors, search],
  );

  function openCreate() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(advisor: Advisor) {
    setEditing(advisor);
    setFormOpen(true);
  }

  function submitForm(values: AdvisorFormValues) {
    if (editing) {
      updateMutation.mutate({ id: editing.id, ...values });
    } else {
      createMutation.mutate(values);
    }
  }

  function toggleActive(advisor: Advisor) {
    updateMutation.mutate({ id: advisor.id, is_active: !advisor.is_active });
  }

  const formError =
    (editing ? updateMutation.error : createMutation.error) instanceof Error
      ? ((editing ? updateMutation.error : createMutation.error) as Error).message
      : null;

  const deleteError =
    deleteMutation.error instanceof Error ? deleteMutation.error.message : null;

  return (
    <PageSection>
      <TableShell
        toolbar={
          <>
            <SearchInput
              placeholder="Search advisors"
              className="w-[260px]"
              value={search}
              onChange={setSearch}
            />
            <Segmented
              items={["Active", "All"]}
              active={scope}
              onSelect={(value) => setScope(value as "Active" | "All")}
            />
            <span className="ml-auto">
              <Button variant="primary" icon={Plus} onClick={openCreate}>
                New advisor
              </Button>
            </span>
          </>
        }
        head={
          <tr>
            <Th>Advisor</Th>
            <Th>Skills</Th>
            <Th>Contact</Th>
            <Th>Lang</Th>
            <Th align="right">Load</Th>
            <Th>Rota</Th>
            <Th>Status</Th>
            <Th />
          </tr>
        }
        footer={
          <span className="t-caption text-ink-4">
            {advisorsQuery.isPending
              ? "Loading advisors"
              : search.trim()
                ? `${visible.length} of ${advisors.length} advisors`
                : `${advisors.length} advisors`}
          </span>
        }
      >
        {advisorsQuery.isPending ? (
          <TableSkeleton rows={5} cols={COLUMN_COUNT} />
        ) : advisorsQuery.isError ? (
          <TableErrorRow
            colSpan={COLUMN_COUNT}
            message={
              advisorsQuery.error instanceof Error
                ? advisorsQuery.error.message
                : "Could not load advisors."
            }
            onRetry={() => advisorsQuery.refetch()}
          />
        ) : visible.length === 0 ? (
          <tr>
            <td colSpan={COLUMN_COUNT}>
              <EmptyState
                icon={Users}
                title={search.trim() ? "No matching advisors" : "No advisors yet"}
                description={
                  search.trim()
                    ? "No advisor matches this search. Clear it to see the full registry."
                    : "Register an advisor so escalated calls have somewhere to go."
                }
              />
            </td>
          </tr>
        ) : (
          visible.map((advisor) => {
            const contact = advisorContact(advisor);
            return (
              <tr
                key={advisor.id}
                className="group transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <Td>
                  <span className="flex items-center gap-sp-5">
                    <Avatar initials={initials(advisor.full_name)} name={advisor.full_name} />
                    <span className="flex flex-col">
                      <span className="t-ui text-ink-1">{advisor.full_name}</span>
                      {advisor.email ? (
                        <span className="t-caption text-ink-4">{advisor.email}</span>
                      ) : null}
                    </span>
                  </span>
                </Td>
                <Td>
                  <span className="flex flex-wrap items-center gap-sp-2">
                    {advisor.skills.map((skill) => (
                      <Token key={skill} mono={false}>
                        {skill}
                      </Token>
                    ))}
                  </span>
                </Td>
                <Td>
                  {contact ? (
                    <span className="t-mono-s text-ink-3">{contact}</span>
                  ) : (
                    <span className="t-caption text-ink-5">—</span>
                  )}
                </Td>
                <Td>
                  <Token>{advisor.language}</Token>
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">{advisorLoad(advisor)}</span>
                </Td>
                <Td>
                  {advisor.is_on_call ? (
                    <Token mono={false}>Rota</Token>
                  ) : (
                    <span className="t-caption text-ink-5">—</span>
                  )}
                </Td>
                <Td>
                  <StatusChip status={advisorStatusKey(advisor)} />
                </Td>
                <Td align="right">
                  <span className="inline-flex items-center gap-sp-1 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
                    <IconButton
                      label={`Edit ${advisor.full_name}`}
                      icon={Pencil}
                      size="sm"
                      onClick={() => openEdit(advisor)}
                    />
                    <IconButton
                      label={
                        advisor.is_active
                          ? `Deactivate ${advisor.full_name}`
                          : `Activate ${advisor.full_name}`
                      }
                      icon={Power}
                      size="sm"
                      onClick={() => toggleActive(advisor)}
                    />
                    <IconButton
                      label={`Delete ${advisor.full_name}`}
                      icon={Trash2}
                      size="sm"
                      onClick={() => setDeleting(advisor)}
                    />
                  </span>
                </Td>
              </tr>
            );
          })
        )}
      </TableShell>

      <AdvisorFormModal
        open={formOpen}
        advisor={editing}
        pending={createMutation.isPending || updateMutation.isPending}
        serverError={formError}
        onClose={() => {
          setFormOpen(false);
          setEditing(null);
          createMutation.reset();
          updateMutation.reset();
        }}
        onSubmit={submitForm}
      />

      <DeleteAdvisorModal
        advisor={deleting}
        pending={deleteMutation.isPending}
        serverError={deleteError}
        onClose={() => {
          setDeleting(null);
          deleteMutation.reset();
        }}
        onConfirm={() => {
          if (deleting) deleteMutation.mutate(deleting.id);
        }}
      />
    </PageSection>
  );
}
```

> **`SearchInput` is currently uncontrolled** — it takes `placeholder` and `className` only. The
> page above passes `value`/`onChange`. Add the two optional props, leaving the class string
> untouched (modification **H** in the checklist):
>
> ```tsx
> export function SearchInput({ placeholder, className, value, onChange }: {
>   placeholder: string;
>   className?: string;
>   value?: string;
>   onChange?: (value: string) => void;
> }) {
>   …
>   <input
>     type="search"
>     placeholder={placeholder}
>     value={value}
>     onChange={(e) => onChange?.(e.target.value)}
>     className="…unchanged…"
>   />
> ```
>
> Both `Checkbox` and `SearchInput` were written as display-only mock components. Making them
> controlled is the minimum change that lets real state exist, and it changes **no** class string,
> no size, no colour. Every other page that renders them keeps working, because both new props are
> optional and the components stay uncontrolled when they are omitted.

---

### File F — `src/lib/nexus/data.ts` *(modify)*

Delete the `ADVISORS` export entirely — the 33 lines from `export const ADVISORS = [` through its
closing `];`. It is now dead: file **E** was its only consumer.

**Do not touch `ADVISOR_TEAM`** (used by `overview.tsx`) or any other export in this file. They
belong to their own cookbooks and removing them now would break routes this feature does not own.

---

## 7. Validation checklist

### 7.1 Constraint compliance

- [ ] **Backend untouched.** `git status --porcelain` lists nothing under `apps/`, `packages/`,
      `services/`. Zero endpoints added, zero business logic written.
- [ ] **CORS / middleware untouched.** No change to `main.py`; verified by the same `git status`.
- [ ] **No new dependencies.** `git diff --name-only -- package.json bun.lock` is empty.
      `zod`, `lucide-react` and `@tanstack/react-query` are all already dependencies.
- [ ] **No new design tokens.** Grep the four new files for `#`, `rgb(`, and Tailwind palette
      classes (`red-`, `blue-`, `green-`, `slate-`, `zinc-`): zero hits. Every class resolves to
      `surface-*`, `ink-*`, `stroke-*`, `rounded-r-*`, `sp-*`, `t-*`, `n-*`, `shadow-elev-*`.
- [ ] **`status.ts` unmodified** — the STATUS truth table gained no keys.
- [ ] `routeTree.gen.ts` diff is empty (no route added or renamed; `/advisors` already existed).

### 7.2 Static

- [ ] `bun --bun tsc --noEmit` exits 0.
- [ ] `bun run lint` shows no new errors beyond the documented prettier baseline.
- [ ] `bun --bun run build` exits 0.

### 7.3 Functional — with `business-api` up

- [ ] `/advisors` renders rows from the database. Cross-check the count against
      `SELECT count(*) FROM routing.advisors WHERE is_active;`
- [ ] **No blank Status cell.** Set one advisor to `available` and one to `busy` in the database:
      they must render **Online** and **On call**. *(This is the §5.1 regression test — the single
      most important assertion in this cookbook.)*
- [ ] Deactivated advisor renders **Inactive**, whatever its `status` column says.
- [ ] `Active` / `All` toggle changes the row count and sends `include_inactive` accordingly.
- [ ] Search filters on name, email, phone and skill; footer switches to "N of M advisors".
- [ ] Create with name + phone → 201, row appears, list refetches.
- [ ] Create with neither phone nor SIP → blocked client-side, message shown, **no request sent**.
- [ ] Create with no name → blocked client-side.
- [ ] Edit: clear the email by emptying the field → the email is actually cleared after refetch.
      *(Confirms the empty-string-not-null rule of §2.4.)*
- [ ] Capacity spinner refuses 0 and negatives; typing `0` and submitting is rejected before the
      request.
- [ ] Skills `Billing, BILLING, general` collapse to `billing, general`.
- [ ] Deactivate → row shows **Inactive** under `All`, disappears under `Active`.
- [ ] Reactivate restores it.
- [ ] Delete → confirmation names the cascade; confirming removes the row.
- [ ] Delete on an advisor with `active_calls > 0` → confirm button disabled, explanation shown.
- [ ] Modal: Escape closes, backdrop click closes, focus lands in the panel on open and returns to
      the trigger on close, background does not scroll.

### 7.4 Failure paths

- [ ] Stop `business-api` → the table shows `TableErrorRow` with a retry, **not** a blank page and
      not an infinite skeleton.
- [ ] Restart it → **Try again** recovers without a full reload.
- [ ] Force a 400 (e.g. patch an advisor to clear both phone and SIP via a crafted request) → the
      backend's own message surfaces inside the modal, and the modal stays open with input intact.
- [ ] Sign out in a second tab, then act in the first → the 401 path from Feature 0 engages; no
      silent failure.

### 7.5 Design fidelity

- [ ] Screenshot-compare a row against `customers.tsx`: identical row height (52px), identical
      hover, identical `Th` treatment.
- [ ] The modal's radius, border, surface and shadow are indistinguishable from a `Card` beside it.
- [ ] Action icons appear on hover **and** on keyboard focus (`focus-within:opacity-100`) — they
      must not be keyboard-unreachable.

### 7.6 Modifications to shared primitives

- [ ] **G** — `Checkbox` gained optional `checked`/`onChange`; class string byte-identical.
- [ ] **H** — `SearchInput` gained optional `value`/`onChange`; class string byte-identical.
- [ ] Every existing usage of both still compiles and renders unchanged (they omit the new props).

---

## 8. Open items

### 8.1 "Handled" volume per advisor does not exist — needs your decision *(non-blocking)*

The template promised a per-advisor handled count. There is no counter on `routing.advisors`, no
aggregate in `advisors.py`, and no join available from the registry to the conversation record.
Producing it would mean **writing new business logic** — aggregating sessions or escalations per
advisor — which constraint 3 forbids me from doing unilaterally.

I dropped the column. Three ways forward, your call:

- **(A)** Leave it dropped. The registry describes capability and reachability; volume belongs on
  Analytics.
- **(B)** Add it to the **Analytics** cookbook if `repositories.py` turns out to expose an
  advisor-keyed aggregate. I will confirm when I read that file for the KPIs feature.
- **(C)** Authorise an additive read-only aggregate endpoint as an approved exception, if and only
  if the underlying data already links sessions to advisors.

**I recommend (B)** — decide after the Analytics extraction, when we know whether the data exists
at all rather than guessing now.

### 8.2 Should an admin be able to set `status` by hand? *(non-blocking, defaults to yes)*

`status` is co-owned: `claim_advisor` and `release_advisor` write it automatically, and PATCH lets
a human overwrite it. An admin setting `available` on someone whose phone is off produces exactly
the failure mode the model's docstring accepts by design — "a stale 'available' flag costs one
unanswered ring". Since the backend permits it and the cost is bounded and documented, I left the
control in the form. Say the word and I will make it read-only in the UI, with `is_active` and the
rota flag as the only human-owned toggles.

### 8.3 Client-side filtering has a ceiling *(informational)*

Sound for a roster in the tens or low hundreds (§5.6). Past roughly a thousand advisors, the
full-table fetch becomes the bottleneck and this should become a server-side search plus
pagination — an additive endpoint, permissible under constraint 3(c) when the need is real.

### 8.4 A delete/release race exists in the backend *(flagged, not fixed)*

Deleting an advisor with `active_calls > 0` destroys the row that `release_advisor` will look up
when the call ends; the release then 404s and the decrement is lost. The UI declines to initiate
this, but a direct API call still can. Fixing it properly means a backend guard — refusing the
delete while `active_calls > 0` — which is a business-logic change and therefore **out of bounds
for me under constraint 2.** Recording it as a backend defect for your triage.

### 8.5 Still unanswered from earlier phases

- **Target branch** — you have applied Feature 0 to a local `version_80`. Confirm that later
  cookbooks target the same branch so I keep referencing it consistently.
- **§8.1 of Feature 0** — the authentication stop-gap (A / B / C). Unresolved, and it does not
  block this feature, but it stays open until a real identity provider is chosen.

---

## 9. What comes next

**Cookbook 2 — Advisor availability**: the weekly shift grid, dated absences and the coverage
report, built on `availability.py` (`c72adb59`) and the five schedule/time-off endpoints. It
depends on this feature for advisor identity and will reuse `Modal` from file C and
`advisorStatusKey` from file B.

One thing I already know I must verify there, and will: the `PUT /schedule` endpoint replaces an
advisor's **entire** weekly grid in one call and rejects overlapping windows, so the editor has to
be a whole-grid editor with client-side overlap detection — not per-row saves.
