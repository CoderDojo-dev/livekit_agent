# Cookbook 13 — Escalations & Human Handoff

**Branch of truth:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Apply onto:** local `version_80`
**Scope:** `Frontend/admin_dashboard/` + **zero** backend files modified
**Depends on:** Feature 0 (substrate), Feature 4 (`sessions.server.ts`), Feature 9 (`delta?` optional in `blocks.tsx`)

---

## 0. Blocking decisions (read before writing code)

### 0.1 — `/conversations` cannot be built as designed. The channel is hardcoded.

The template at `src/routes/conversations.tsx` (`99ead9ea`) is a **live chat inbox**: a thread list with `live` presence dots, a message thread with customer/AI/advisor bubbles, and a reply composer (`Write a reply` + `Send` + `Attach`).

The worker cannot produce any of it. In `apps/agent-worker/src/conversation/writer.py` (`fbfea025`), `start_session` writes:

```python
self._enqueue("session_start", {
    ...
    "start_time": self._start_time,
    "channel": "voice",          # <-- hardcoded, not a parameter
})
```

`channel` is accepted by the schema (`CheckConstraint("channel IN ('voice','chat')")`) but **no code path ever writes `'chat'`**. There is exactly one writer and it is the LiveKit voice worker.

Consequences, stated as facts rather than opinions:

1. A conversations page filtered to `channel='chat'` is **permanently empty**. Not empty-for-now — empty by construction.
2. The reply composer targets an **inbound message path that does not exist**. There is no endpoint, no queue, no adapter. Building one is new business logic → **Constraint 3 forbids it**.
3. The `live` flag has no backend source. `CallSession` has `end_time`, but a live-call feed would require realtime transport the business-api does not have (Cookbook 12 established the worker exposes no HTTP surface at all).
4. The right-hand **Ingestion** panel duplicates `/knowledge`, which Cookbook 6 already wired to `knowledge-service:8102`. Two upload surfaces for one corpus is a defect, not a feature.

**Decision: `/conversations` is retired and its route repurposed.** Shipping a chat inbox over a voice-only platform would be the single most dishonest screen in the console.

### 0.2 — What replaces it: the last unwired existing endpoint

Audit of `main.py` (`ff52daff`) against Cookbooks 1–12 leaves exactly one existing, role-gated, never-wired route:

```python
@app.get("/api/v1/escalations")   # SuperviseurRole; status="open"
```

It is backed by `SupervisionRepository.escalations()` over `conversation.escalation_cases`, and it answers a question no current screen answers: **when the AI gave up, what did it hand to the human, and was that handoff ever closed?**

That is squarely admin-relevant, it is the natural semantic successor to "conversations" (both are about the human side of an exchange), and it requires **zero backend changes**. Cookbooks 4, 8, 9, 10, 11 and 12 each needed a new read; this one needs none.

### 0.3 — Route rename, and why the churn is worth it

The path is renamed `/conversations` → `/escalations`. Keeping the old path while the page says "Escalations" leaves a URL that lies, and URLs get pasted into tickets and shared with colleagues.

This is a three-file change (`nav.ts`, new route file, `routeTree.gen.ts`) plus deletion of the old route — the same shape as Cookbook 8's `/decisions` addition. Shortcut **`G E`** (`G A` Advisors, `G D` Availability, `G K` Decisions are taken).

---

## 1. Correction to Cookbook 4 — the reported 500 is not a nullability bug

Cookbook 4 flagged `session_detail` as a live 500:

```python
"max_frustration": float(call.max_frustration_score),   # repositories.py
```

on the theory that the column is nullable. **Reading the model, that theory is wrong.** In `packages/persistence/src/persistence/models/conversation.py` (`ec4592ad`):

```python
max_frustration_score: Mapped[float] = mapped_column(
    Numeric(5, 2), nullable=False, server_default=text("0")
)
```

`NOT NULL DEFAULT 0`. `float(...)` cannot receive `None` from a schema-conformant row, so **the null-guard proposed in Cookbook 4 §8.7 is unnecessary and must not be applied as written.**

Two honest caveats, because I would rather over-report than quietly reverse myself:

- The defensive style elsewhere in the same file — `func.coalesce(func.avg(...), 0)` in `kpis()`, `float(s.max_frustration_score or 0.0)` in `telemetry_timeline()` — suggests the authors were themselves unsure. That is a smell, not evidence.
- If the column was added by a later migration **without a backfill**, existing rows could hold `NULL` in a running database despite the model. The schema is authoritative for new deployments; a live database can disagree.

**MUST-VERIFY (one line, decides it):**

```sql
SELECT count(*) FROM conversation.call_sessions WHERE max_frustration_score IS NULL;
```

`0` → close Cookbook 4 §8.7 as invalid and drop the guard. `> 0` → the deployed schema drifted from the model; keep the guard **and** backfill, because the drift affects `kpis()` and every aggregate.

This matters here specifically: escalated sessions are the ones this page links to.

---

## 2. Backend reference (read-only, verbatim)

### 2.1 Model — `conversation.escalation_cases`

```python
class EscalationCase(UUIDPrimaryKey, Base):
    __tablename__ = "escalation_cases"
    __table_args__ = (
        CheckConstraint("target IN ('manager_agent','human_advisor')", name="target"),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('transferred','queued','callback_scheduled','resolved')",
            name="resolution",
        ),
        {"schema": "conversation"},
    )

    session_id:  Mapped[uuid.UUID]        # FK conversation.call_sessions.id, NOT NULL
    customer_id: Mapped[uuid.UUID | None] # FK crm.customers.id
    trigger:     Mapped[str]              # String(40), NOT NULL, "spec Appendix A"
    target:      Mapped[str]              # String(20), NOT NULL
    dossier:     Mapped[dict]             # JSONB, NOT NULL
    resolution:  Mapped[str | None]       # String(20)
    created_at:  Mapped[datetime]         # NOT NULL, server_default now()
```

### 2.2 Repository — `SupervisionRepository.escalations()`

```python
def escalations(self, status: str = "open") -> list[dict]:
    rows = self._s.scalars(select(EscalationCase).order_by(EscalationCase.created_at.desc())).all()
    out = []
    for case in rows:
        is_open = case.resolution is None
        if status == "open" and not is_open:
            continue
        out.append({
            "id": str(case.id), "session_id": str(case.session_id), "trigger": case.trigger,
            "target": case.target, "resolution": case.resolution, "dossier": case.dossier,
        })
    return out
```

### 2.3 Writer — how an escalation is created

```python
def record_escalation(self, trigger: str, target: str, dossier: dict, customer_id=None) -> None:
    ...
    self._enqueue("escalation", {
        "session_id": uuid.UUID(self._session_db_id),
        "customer_id": to_uuid(customer_id),
        "trigger": trigger, "target": target, "dossier": dossier,
    })
```

`resolution` is **never written by the worker**. It is `NULL` at creation and nothing in the agent-worker ever sets it. See §8.2.

---

## 3. Contract table (authoritative for this cookbook)

| Field | Type | Present in response? | Notes |
|---|---|---|---|
| `id` | `string` (uuid) | yes | React key |
| `session_id` | `string` (uuid) | yes | cross-link to Feature 4 |
| `trigger` | `string` | yes | open vocabulary, `String(40)` |
| `target` | `string` | yes | `manager_agent` \| `human_advisor` |
| `resolution` | `string \| null` | yes | `null` = open |
| `dossier` | `object` | yes | arbitrary JSONB |
| `created_at` | — | **NO** | ordered by it, never returned — §4.2 |
| `customer_id` | — | **NO** | on the model, dropped by the repo — §8.3 |

---

## 4. Four traps in this endpoint

### 4.1 `status` is not a filter — it is a single magic word

```python
if status == "open" and not is_open: continue
```

Only the literal string `"open"` filters. **Every other value — `"resolved"`, `"all"`, `""`, `"banana"` — returns every row.** Passing `status=resolved` would silently return open cases too.

**Binding rule:** the UI sends exactly two values — `"open"` or `"all"` — and `"all"` is understood as *"any non-`open` string"*, not as a supported enum member. Never expose a per-resolution server filter; filter those client-side.

This is the third variant of the empty-filter problem: C3 `if status:` (empty = All), C5 omit-entirely, and now C13 magic-word.

### 4.2 There is no timestamp in the response

The query orders by `created_at.desc()`; the dict omits it. So the **order is meaningful but unrenderable as a value**.

**Decision: render no time at all, and preserve server order.** The list is labelled *"Most recent first"* — which is true and provable — and no relative-time string is invented. Fabricating "2h ago" from a missing field is exactly the class of lie C9 §0 banned.

Rejected: adding `"created_at": case.created_at.isoformat()` to the dict. It is one additive line and JSON-additive changes are backward compatible — but `apps/supervisor-dashboard` also consumes this API, and Constraint 2 locks existing backend behaviour. Drafted in §8.1, **not shipped**.

### 4.3 `status=all` is unbounded

No `LIMIT`, no pagination — `select(EscalationCase)` loads the entire table. Same class as `/audit/verify` (C10). Mitigation: the page **defaults to Open**, and the All view renders a row-count caption so growth is visible. Flagged §8.4.

### 4.4 `dossier` is arbitrary JSONB

C10 deliberately did **not** render audit `payload`. Here the dossier *is* the feature — it is the context handed to the human — so it must render, but generically: scalars as key/value rows, everything else as compact JSON. No assumed keys.

---

## 5. Status vocabulary — eleventh chip trap, thirteenth clean cookbook

`resolution` values vs `src/lib/nexus/status.ts` (`84449b29`), whose contract is `const def = STATUS[status]; if (!def) return null;` — **an unmapped value renders nothing at all**.

| Backend | In `status.ts`? | Mapped to | Reasoning |
|---|---|---|---|
| `null` | — | `open` | Unresolved handoff. `open` is canonical. |
| `transferred` | no | `in_progress` | Handed to a human; work continues elsewhere. Not terminal. |
| `queued` | **yes** | `queued` | Exact match. |
| `callback_scheduled` | no | `pending` | Committed to future work, nothing happening now. |
| `resolved` | **yes** | `resolved` | Exact match. |

`target` (`manager_agent` / `human_advisor`) is **not a status** — no chip. Rendered with `Token`.
`trigger` is an open `String(40)` vocabulary — **no chip**, `Token` with a humanized label, unknown values pass through verbatim (Cookbook 12's drift rule).

**Zero changes to `status.ts`. Thirteenth consecutive cookbook.**

---

## 6. Files

**New**
- `src/lib/api/escalations.server.ts`
- `src/lib/nexus/escalation-view.ts`
- `src/routes/escalations.tsx`

**Modified**
- `src/lib/nexus/query-keys.ts` — `+ escalationKeys`
- `src/lib/nexus/nav.ts` — `/conversations` entry → `/escalations`, `PAGE_META`, shortcut `G E`
- `src/lib/nexus/data.ts` — remove `ConversationRow`, `CONVERSATIONS`, `Bubble`, `THREAD`
- `routeTree.gen.ts` — regenerated

**Deleted**
- `src/routes/conversations.tsx`

**Not touched:** `INGESTED_FILES` — grep first, Cookbook 6 may still reference it from `/knowledge`. See Check 6.

---

## 7. Code

### 7.1 `src/lib/api/escalations.server.ts`

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/client";
import { authedMiddleware, inputValidator, requireRole } from "@/lib/api/middleware";

/** Exactly the six keys the repository returns. No timestamp, no customer_id. */
export type Escalation = {
  id: string;
  session_id: string;
  trigger: string;
  target: string;
  resolution: string | null;
  dossier: Record<string, unknown>;
};

/**
 * The backend treats ONLY the literal "open" as a filter; every other value
 * returns all rows. "all" is our sentinel for that branch, not a server enum.
 */
export const escalationScope = z.enum(["open", "all"]);
export type EscalationScope = z.infer<typeof escalationScope>;

export const listEscalations = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator(inputValidator(z.object({ scope: escalationScope.default("open") })))
  .handler(async ({ data, context }) => {
    const rows = await businessApi<Escalation[]>("/api/v1/escalations", {
      method: "GET",
      query: { status: data.scope },
      role: context.session.role,
    });
    return Array.isArray(rows) ? rows : [];
  });
```

Notes:
- `requireRole("superviseur")` — the **factory** form (Feature 2 correction #1), matching the route's `SuperviseurRole`.
- `GET`, not `POST`: read-only, so the React Start CSRF rule (Feature 2 correction #2) is not triggered.
- The response is a bare array, not an envelope — verified against `main.py`, same shape family as `/actions` and `/policy/verdicts`.

### 7.2 `src/lib/nexus/escalation-view.ts`

```ts
import type { Escalation } from "@/lib/api/escalations.server";

/**
 * resolution -> canonical status.ts key. null means "never resolved" = open.
 * Unknown values fall back to "open" so a StatusChip never renders empty
 * (StatusChip returns null for unmapped keys).
 */
export function escalationStatusKey(resolution: string | null): string {
  switch (resolution) {
    case null:
    case undefined:
      return "open";
    case "transferred":
      return "in_progress";
    case "queued":
      return "queued";
    case "callback_scheduled":
      return "pending";
    case "resolved":
      return "resolved";
    default:
      return "open";
  }
}

export function isOpen(e: Escalation): boolean {
  return e.resolution === null || e.resolution === undefined;
}

const TARGET_LABEL: Record<string, string> = {
  manager_agent: "Manager agent",
  human_advisor: "Human advisor",
};

/** CheckConstraint allows exactly two values; unknown passes through verbatim. */
export function targetLabel(target: string): string {
  return TARGET_LABEL[target] ?? target;
}

/** trigger is an open String(40) vocabulary. Humanize, never invent. */
export function triggerLabel(trigger: string): string {
  if (!trigger) return "unknown";
  return trigger.replace(/[_-]+/g, " ").trim();
}

export function resolutionLabel(resolution: string | null): string {
  if (!resolution) return "Open";
  return resolution.replace(/[_-]+/g, " ");
}

export type DossierEntry = { key: string; label: string; value: string; long: boolean };

/**
 * Flatten one level of an arbitrary JSONB dossier.
 * Scalars render inline; objects/arrays render as compact JSON in a wrapped block.
 * No key is assumed to exist.
 */
export function dossierEntries(dossier: unknown): DossierEntry[] {
  if (!dossier || typeof dossier !== "object" || Array.isArray(dossier)) return [];
  return Object.entries(dossier as Record<string, unknown>).map(([key, raw]) => {
    let value: string;
    let long = false;
    if (raw === null || raw === undefined) {
      value = "—";
    } else if (typeof raw === "string") {
      value = raw;
      long = raw.length > 60;
    } else if (typeof raw === "number" || typeof raw === "boolean") {
      value = String(raw);
    } else {
      value = JSON.stringify(raw);
      long = true;
    }
    return { key, label: key.replace(/[_-]+/g, " "), value, long };
  });
}

export function escalationMatches(e: Escalation, q: string): boolean {
  const n = q.trim().toLowerCase();
  if (!n) return true;
  return (
    e.trigger.toLowerCase().includes(n) ||
    e.target.toLowerCase().includes(n) ||
    e.session_id.toLowerCase().includes(n) ||
    (e.resolution ?? "open").toLowerCase().includes(n)
  );
}
```

No `new Date`, no `getDay`, no `getHours`, no `toLocaleString` — there is no timestamp to mishandle (§4.2), so the date trap is structurally absent.

### 7.3 `src/lib/nexus/query-keys.ts` (additive)

```ts
export const escalationKeys = {
  all: ["escalations"] as const,
  list: (scope: string) => ["escalations", "list", scope] as const,
};
```

### 7.4 `src/lib/nexus/nav.ts`

Replace the `/conversations` entry **in place** (same section, same position — no reordering):

```ts
{ label: "Escalations", to: "/escalations", icon: LifeBuoy, shortcut: "G E" },
```

and in `PAGE_META`:

```ts
"/escalations": {
  title: "Escalations",
  subtitle: "Handoffs from the AI to a manager agent or a human advisor.",
},
```

Remove the `"/conversations"` key from both. `LifeBuoy` is already available from `lucide-react`; if the existing entry's icon is preferred, keep it rather than introducing a new one.

### 7.5 `src/routes/escalations.tsx`

```tsx
import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { listEscalations, type Escalation } from "@/lib/api/escalations.server";
import {
  dossierEntries,
  escalationMatches,
  escalationStatusKey,
  resolutionLabel,
  targetLabel,
  triggerLabel,
} from "@/lib/nexus/escalation-view";
import { escalationKeys } from "@/lib/nexus/query-keys";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/escalations")({
  head: () => ({
    meta: [
      { title: "Escalations — Nexus" },
      {
        name: "description",
        content: "Handoffs from the AI to a manager agent or a human advisor, with the context dossier.",
      },
      { property: "og:title", content: "Escalations — Nexus" },
      { property: "og:description", content: "Every AI-to-human handoff and its dossier." },
    ],
  }),
  component: EscalationsPage,
});

function EscalationsPage() {
  const [scope, setScope] = useState<"open" | "all">("open");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const query = useQuery({
    queryKey: escalationKeys.list(scope),
    queryFn: () => listEscalations({ data: { scope } }),
  });

  const rows = useMemo(
    () => (query.data ?? []).filter((e) => escalationMatches(e, q)),
    [query.data, q],
  );

  const current: Escalation | undefined =
    rows.find((e) => e.id === selected) ?? rows[0];

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[360px_1fr]">
      {/* ---------- List ---------- */}
      <Card padded={false} className="overflow-hidden">
        <div className="flex items-center justify-between gap-sp-5 border-b border-stroke-subtle p-sp-6">
          <span className="t-micro text-ink-5">Handoffs</span>
          <Segmented
            options={[
              { label: "Open", value: "open" },
              { label: "All", value: "all" },
            ]}
            value={scope}
            onChange={(v: string) => {
              setScope(v as "open" | "all");
              setSelected(null);
            }}
          />
        </div>

        <div className="border-b border-stroke-subtle p-sp-6">
          <SearchInput
            placeholder="Search trigger, target or session"
            value={q}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQ(e.target.value)}
          />
        </div>

        {query.isPending ? (
          <div className="p-sp-6">
            <CardSkeleton />
          </div>
        ) : query.isError ? (
          <div className="p-sp-6">
            <ErrorState
              message={errorMessage(query.error)}
              onRetry={() => void query.refetch()}
            />
          </div>
        ) : rows.length === 0 ? (
          <div className="p-sp-7">
            <EmptyState
              icon={ShieldAlert}
              title={scope === "open" ? "No open escalations" : "No escalations recorded"}
              description={
                scope === "open"
                  ? "Every handoff has been closed out."
                  : "The agent has not handed a call to a human yet."
              }
            />
          </div>
        ) : (
          <>
            <ul className="max-h-[640px] overflow-y-auto">
              {rows.map((e) => {
                const active = current?.id === e.id;
                return (
                  <li key={e.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(e.id)}
                      className={cn(
                        "flex w-full items-start gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5 text-left transition-colors duration-[120ms]",
                        active ? "bg-surface-3" : "hover:bg-surface-3/60",
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="t-ui block truncate text-ink-1">
                          {triggerLabel(e.trigger)}
                        </span>
                        <span className="t-caption block truncate text-ink-4">
                          {targetLabel(e.target)}
                        </span>
                      </span>
                      <StatusChip status={escalationStatusKey(e.resolution)} />
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-6 py-sp-5">
              <Token>{rows.length} shown</Token>
              <span className="t-caption ml-auto text-ink-5">Most recent first</span>
            </div>
          </>
        )}
      </Card>

      {/* ---------- Dossier ---------- */}
      <Card padded={false}>
        {!current ? (
          <div className="p-sp-7">
            <EmptyState
              icon={ShieldAlert}
              title="No handoff selected"
              description="Choose an escalation to read the dossier handed to the human."
            />
          </div>
        ) : (
          <>
            <div className="p-sp-7">
              <CardHeader
                title={triggerLabel(current.trigger)}
                subtitle={`Handed to ${targetLabel(current.target)}`}
              />
            </div>

            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Outcome</span>
              <span className="ml-auto flex items-center gap-sp-4">
                <span className="t-ui text-ink-2">{resolutionLabel(current.resolution)}</span>
                <StatusChip status={escalationStatusKey(current.resolution)} />
              </span>
            </div>

            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Session</span>
              <span className="t-mono ml-auto truncate text-ink-3">{current.session_id}</span>
            </div>

            <div className="mt-sp-7 px-sp-7">
              <CardHeader
                title="Context dossier"
                subtitle="Exactly what the agent handed over. Recorded at handoff time."
              />
            </div>

            {dossierEntries(current.dossier).length === 0 ? (
              <div className="px-sp-7 pb-sp-7 pt-sp-5">
                <p className="t-caption text-ink-5">The dossier is empty.</p>
              </div>
            ) : (
              <ul className="mt-sp-5">
                {dossierEntries(current.dossier).map((d) => (
                  <li
                    key={d.key}
                    className="border-t border-stroke-subtle px-sp-7 py-sp-5 last:border-b-0"
                  >
                    {d.long ? (
                      <div className="min-w-0">
                        <p className="t-label text-ink-3">{d.label}</p>
                        <p className="t-mono mt-sp-3 break-words text-ink-2">{d.value}</p>
                      </div>
                    ) : (
                      <div className="flex items-center gap-sp-5">
                        <span className="t-label text-ink-3">{d.label}</span>
                        <span className="t-mono-l ml-auto truncate text-ink-1">{d.value}</span>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
    </PageSection>
  );
}
```

**Design-system compliance.** Every class is lifted from the captured inventory: the list button, `border-b border-stroke-subtle last:border-b-0`, `t-label ml-auto text-ink-3`, `t-mono-l ml-auto text-ink-1`, `mt-sp-7`, `flex items-center gap-sp-5`. No new colour, radius, spacing token or typography class. The three-column template collapses to two because the third column was the ingestion duplicate.

**No `Modal`** — the detail is an inline column, so the `PageSection` `.rise` containing-block trap (Feature 1 defect 3) is not reachable here.

**Call-site checks carried forward:** `SearchInput` may not forward `value`/`onChange`, and `Segmented` may not accept `options/value/onChange` in that exact shape. Both are verified in Checks 3–4 and adjusted to the real signatures at apply time; the local `Segmented` already carries the Feature 1 `type="button"` fix.

---

## 8. Open items — decisions I did not make alone

### 8.1 Expose `created_at` (drafted, **not shipped**)

One additive line in `repositories.py`:

```python
"created_at": case.created_at.isoformat(),
```

Without it the page cannot answer *"how long has this handoff been open?"* — the single most operationally useful question about an escalation. JSON-additive changes do not break consumers, but `apps/supervisor-dashboard` also reads this endpoint and Constraint 2 locks existing backend behaviour. **Needs your approval.** If granted, add a `formatInstant`-style column and reuse Cookbook 8's helper rather than writing a third date formatter (§8.4 of C8 still stands).

### 8.2 Nothing ever sets `resolution`

The worker writes escalations with `resolution = NULL` and **no code path anywhere sets it**. So in the current system every escalation is open forever, and the Open/All toggle will show identical lists.

This is a genuine backend gap, not a UI problem. Closing a handoff is new business logic → **Constraint 3: flagged, not built.** The mapping table in §5 is written so that the moment a resolution path exists, the UI renders it correctly with no changes.

Worth deciding: should closing an escalation be an admin action, or should it be derived from the linked session's `final_disposition`?

### 8.3 `customer_id` is dropped by the repository

The model has it; `escalations()` does not return it. So this page cannot link to Customer 360 (Cookbook 11) even though the data exists one join away. Same additive-line question as §8.1.

### 8.4 `status=all` is unbounded

No limit, no pagination. Fine at current volume, degrades linearly forever. Cheapest fix is a `limit` parameter with a clamp, matching C10's keyset pattern — again additive, again needs approval.

### 8.5 Cross-link to the session transcript

`session_id` is displayed but not clickable. Feature 4 owns session detail, so a link is one line — but only after §1's MUST-VERIFY confirms opening an escalated session does not 500. **Sequenced deliberately after the SQL check.**

### 8.6 `/rules` is now the only orphan left

With `/conversations` retired, `/rules` is the last template page with no wiring. Cookbook 7 §8.1 flagged that it overlaps `/policies`, which is already wired to `/api/v1/reference/business-rules`. My recommendation: **retire `/rules` too** rather than build a second view of one dataset — but that is your call, and it is the last one outstanding.

---

## 9. Validation checklist

1. `bunx tsc --noEmit` → clean.
2. `bun run lint` → exactly **36 problems** (28 prettier errors + 8 warnings). Any other count means this patch changed the baseline.
3. `bun run build` → exit 0.
4. `grep -rn "options=\|value=\|onChange=" src/components/nexus/primitives.tsx` → confirm the real `Segmented` and `SearchInput` signatures; adjust call sites if they differ.
5. `grep -rn "CONVERSATIONS\|THREAD\|ConversationRow\|Bubble" src/` → **zero hits** after deletion.
6. `grep -rn "INGESTED_FILES" src/` → if `/knowledge` still uses it, **leave it in `data.ts`**; only delete when this is the last reference.
7. `grep -rn "/conversations" src/` → zero hits (nav, routeTree, links).
8. `grep -rn "escalations" src/lib/nexus/nav.ts` → one entry, shortcut `G E`, unchanged section order.
9. `git diff --stat -- apps/ packages/ services/` → **empty**. Zero backend files touched.
10. `git diff --stat -- Frontend/admin_dashboard/package.json` → empty. Zero new dependencies.
11. `git diff -- src/lib/nexus/status.ts` → empty. **Thirteenth consecutive cookbook.**
12. `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/escalations.tsx src/lib/nexus/escalation-view.ts` → no hits.
13. `grep -n 'getDay(\|getHours(\|new Date(\|toLocaleString(' src/routes/escalations.tsx src/lib/nexus/escalation-view.ts` → no hits.
14. Navigate `/escalations` → Open selected by default, first row auto-selected, dossier renders.
15. Toggle **All** → request carries `status=all`; confirm in the network tab that it is the proxy origin, **not** `:8108` directly.
16. Search `manager` → list narrows, selection falls back to the first visible row without crashing.
17. Seed one escalation with `dossier = '{}'` → "The dossier is empty." No blank panel.
18. Seed `dossier` with a nested object → renders as compact JSON in the wrapped block, no overflow.
19. Seed `resolution = 'transferred'` → chip renders **in progress**, never blank. Repeat for all four values plus `NULL`.
20. Seed `resolution = 'not_a_real_value'` (direct SQL, bypassing the constraint via a disabled check) → falls back to `open`, never blank.
21. Log in as `conseiller` → 403 handled by the substrate's forbidden state, no retry storm (QueryClient retries false on 401/403).
22. Empty table → correct EmptyState copy for each scope.
23. `SELECT count(*) FROM conversation.call_sessions WHERE max_frustration_score IS NULL;` → record the result and close or keep Cookbook 4 §8.7 accordingly (§1).
