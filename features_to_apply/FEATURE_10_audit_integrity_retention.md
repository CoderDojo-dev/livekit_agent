# Cookbook 10 - Audit, Integrity & Retention (`/settings`)

**Branch of record:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Working branch:** `version_80`
**Scope:** admin dashboard only.
**Backend changes:** +1 repository method, +1 route (read-only). **Zero modifications to existing backend logic.**
**One backend safety change is RECOMMENDED but NOT shipped** - it modifies existing behaviour and needs your approval (S8.1).

---

## S0 - Why this feature, and the decision that shapes it

Every admin page with real backing is now covered. What remains is the inverse problem: three
**real, working, `administrateur`-gated backend features that have no frontend at all.**

| Endpoint | Exists since | Frontend today |
|---|---|---|
| `GET /api/v1/audit/verify` | v79 | none |
| `GET /api/v1/jobs/integrity` | v79 | none |
| `POST /api/v1/jobs/retention` | v79 | none |

And one orphan template page whose own `head` description already promises exactly this:

> `"Workspace configuration, members, roles, API keys and audit."` - `settings.tsx` (`d83ce0cd`)

So Feature 10 pairs the orphan page with the orphan endpoints. No new route, no `nav.ts` change.

### The decision

`POST /api/v1/jobs/retention` is **the single most destructive operation in the entire platform**, and
it is currently reachable by any `administrateur` with a URL bar.

```python
def run_retention(session, retention_days: int = 90, dry_run: bool = True) -> RetentionReport:
    cutoff = cutoff_date(retention_days)
    old_ids = list(session.scalars(select(CallSession.id).where(CallSession.start_time < cutoff)))
```

`cutoff_date(n)` is `datetime.now(UTC) - timedelta(days=n)`. There is **no floor on `n`**:

- `retention_days=0` puts the cutoff at **now**, so `start_time < cutoff` matches **every session ever recorded**.
- A negative value puts the cutoff in the **future** and matches everything too.

With `dry_run=false`, that single request:

1. overwrites `Turn.transcript_masked` with `"[purged]"` for every matched session - **the original text is gone, there is no copy**;
2. calls `store.delete(url)` on every audio recording - **object-storage deletion, outside the database transaction, irreversible**;
3. nulls `audio_record_url`;
4. writes one `data_retention` audit entry and commits.

There is no undo, no soft delete, no snapshot. `Turn` is described in the model as **append-only**;
this job is the one thing in the system that rewrites it.

**Decision: the UI treats retention as a two-phase, typed-confirmation operation, and never as a
button.** A dry run with the exact same `retention_days` is *mandatory* before the real run is
reachable, the blast radius is shown in full, and the operator must type the session count to
proceed. Changing `retention_days` invalidates the dry run and re-locks the purge.

That is a frontend guard, and a frontend guard is not a security control - `curl` bypasses it
entirely. The real fix is a floor in the backend, which **modifies existing behaviour and is therefore
flagged, not shipped** (S8.1, with the exact diff ready).

This extends the rule the series has been building. Cookbook 5: never expose a write an upstream
source will silently revert. Cookbook 7: never expose a number the system does not enforce. Cookbook
9: never render a status the backend did not measure. **Cookbook 10: never expose an irreversible
operation as a single click.**

---

## S1 - Feature name & scope

**Feature 10 - Audit, Integrity & Retention.** Three panels on the existing `/settings` route:

1. **Audit chain** - verify the hash chain; browse recent entries (new read endpoint).
2. **Referential integrity** - run the cross-domain orphan report.
3. **Data retention** - dry run, then guarded purge.

Out of scope: `/rules`, `/conversations` (still no backend - Cookbook 7 S8.1, Cookbook 8 S9);
workspace members / roles / API keys, which the mock's own copy mentions but which have **no backend
whatsoever** (S8.3).

---

## S2 - Backend reference (exact names and paths)

### 2.1 `packages/audit-trail/src/audit_trail/ledger.py` (`9eb4cc04`)

```python
GENESIS_HASH = "0" * 64
_AUDIT_LOCK_KEY = 8472  # pg advisory lock: serialize chain appends within a transaction

def compute_entry_hash(previous_hash: str, payload: dict, timestamp: str) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest_input = f"{previous_hash}|{canonical}|{timestamp}".encode()
    return hashlib.sha256(digest_input).hexdigest()
```

`PgAuditLedger` exposes exactly three methods: **`append`**, **`verify`**, **`count`**.

```python
def verify(self) -> bool:
    rows = list(self._session.scalars(select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.asc())))
    expected_previous = GENESIS_HASH
    for row in rows:
        if row.previous_hash != expected_previous:
            return False
        if compute_entry_hash(row.previous_hash, row.payload, row.created_at.isoformat()) != row.entry_hash:
            return False
        expected_previous = row.entry_hash
    return True
```

Two consequences the frontend must respect:

- **`verify()` materialises the entire ledger and recomputes every SHA-256.** No limit, no pagination,
  no early exit on the happy path. Cost grows linearly and forever - `total_audit_entries` from
  `system_overview` (Cookbook 9) is exactly that number. This is a deliberate, expensive, operator-
  initiated action (F3).
- **There is no list method.** You cannot read audit entries through this class at all (F4).

### 2.2 `packages/persistence/src/persistence/models/audit.py` (`08aab975`)

```python
class AuditLedgerEntry(UUIDPrimaryKey, Base):
    __tablename__ = "audit_ledger"
    __table_args__ = ({"schema": "audit"},)

    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)  # strict chain ordering
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_reference: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

`seq` is the chain order, **not** `created_at` and **not** `id`. Ordering by anything else can present
a chain that looks broken when it is not. No `Timestamps` mixin - there is no `updated_at`, by design:
the table is append-only.

### 2.3 `apps/business-api/src/business_api/jobs/integrity.py` (`b361d748`)

```python
@dataclass
class IntegrityReport:
    orphans: dict
    audit_chain_intact: bool
    audit_entries: int

    @property
    def ok(self) -> bool:
        return self.audit_chain_intact and not any(self.orphans.values())

def run_integrity(session: Session) -> IntegrityReport:
    orphans = {
        "billing.accounts->crm.customers": ...,
        "billing.invoices->crm.customers": ...,
        "ocs.balance_accounts->crm.subscriptions": ...,
        "conversation.call_sessions->crm.customers": ...,
    }
    ledger = PgAuditLedger(session)
    return IntegrityReport(orphans=orphans, audit_chain_intact=ledger.verify(), audit_entries=ledger.count())
```

Four orphan checks, fixed keys, always all four present. `_orphans` filters `fk_attr.is_not(None)`
before `not_in(select(parent.id))`, so the classic `NOT IN` / NULL trap does not apply here - the
parent column is a primary key and can never be NULL. This code is correct.

**`run_integrity` calls `ledger.verify()` internally.** So the integrity job carries the *same* full-
chain cost as the verify endpoint, plus four `COUNT(*)`s. Running both back to back verifies the chain
twice (F5).

### 2.4 `apps/business-api/src/business_api/jobs/retention.py` (`8e6b9322`)

```python
_PURGED = "[purged]"

@dataclass
class RetentionReport:
    cutoff: str
    sessions_matched: int
    turns_anonymized: int
    dry_run: bool

if not dry_run and matched:
    result = session.execute(
        update(Turn)
        .where(Turn.session_id.in_(old_ids), Turn.transcript_masked.is_not(None),
               Turn.transcript_masked != _PURGED)
        .values(transcript_masked=_PURGED)
    )
    turns_anonymized = result.rowcount or 0
    store = get_store()
    if store.enabled:
        for url in session.scalars(...):
            with suppress(Exception):
                store.delete(url)
    session.execute(update(CallSession).where(CallSession.id.in_(old_ids)).values(audio_record_url=None))
    PgAuditLedger(session).append(
        None, "data_retention",
        {"cutoff": ..., "sessions": matched, "turns_anonymized": turns_anonymized},
        entity_reference="retention_job",
    )
    session.commit()
```

Read that guard carefully: **`if not dry_run and matched:`**. Everything destructive is inside it, and
so is `turns_anonymized`. In a dry run the function returns `turns_anonymized=0` **not because no turns
would be affected, but because it never looked**. The dry run reports `sessions_matched` only. Any UI
that shows a dry-run turn count is reporting a fabricated zero (F6).

Note also that `run_retention` **commits internally**, unlike every other mutation in the codebase
where `main.py` owns the commit. And the object-store deletions happen **before** that commit, inside
`with suppress(Exception)` - so blob deletion is irreversible, non-transactional, and silent on
failure (F7).

### 2.5 `main.py` (`ff52daff`) - the three routes, verbatim

```python
@app.get("/api/v1/audit/verify")
def audit_verify(
    session: DbSession,
    role: AdministrateurRole,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> dict:
    """Run the hash-chain integrity check (whole chain; range is a later refinement)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


@app.get("/api/v1/jobs/integrity")
def integrity(session: DbSession, role: AdministrateurRole) -> dict:
    report = run_integrity(session)
    return {
        "ok": report.ok, "orphans": report.orphans,
        "audit_chain_intact": report.audit_chain_intact, "audit_entries": report.audit_entries,
    }


@app.post("/api/v1/jobs/retention")
def retention(
    session: DbSession,
    role: AdministrateurRole,
    retention_days: int = 90,
    dry_run: bool = True,
) -> dict:
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__
```

Three verified facts that change the implementation:

1. **`from_seq` and `to_seq` are accepted and silently ignored.** The docstring admits it - *"range is
   a later refinement"*. A caller who passes a range receives a **whole-chain** result with no
   indication the range was dropped. The UI must therefore expose **no range control** (F2).
2. **`retention` returns `.__dict__`** - a flat `RetentionReport`, **no envelope**, same convention
   break as `/api/v1/kpis` in Cookbook 9. Verified, not assumed.
3. **`retention_days` and `dry_run` are query parameters, not a body.** The route has no Pydantic
   model. A JSON body would be ignored and the defaults (`90`, `dry_run=True`) would apply silently
   (F8).

All three are `AdministrateurRole` - **rank 3**, the strictest gate in the system.

### 2.6 `Frontend/admin_dashboard/src/routes/settings.tsx` (`d83ce0cd`) - the mock

```tsx
function SettingsPage() {
  return (
    <PageSection>
      <Card padded={false}>
        <ul>
          {SETTINGS_SECTIONS.map((s) => (
            <li key={s.name} className="border-b border-stroke-subtle last:border-b-0">
              <button type="button" className="flex w-full items-center gap-sp-5 px-sp-7 py-sp-6 text-left transition-colors duration-[120ms] hover:bg-surface-3">
                <span className="min-w-0">
                  <span className="t-ui block text-ink-1">{s.name}</span>
                  <span className="t-caption block text-ink-4">{s.description}</span>
                </span>
                <ChevronRight size={16} strokeWidth={1.5} aria-hidden="true" className="ml-auto text-ink-5" />
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </PageSection>
  );
}
```

Every row is a `<button>` with **no `onClick`, no `href`, no navigation target**. The whole page is
inert, and the chevron actively promises a destination that does not exist. Classes to reuse verbatim:
`border-b border-stroke-subtle last:border-b-0`, `flex w-full items-center gap-sp-5 px-sp-7 py-sp-6 text-left`,
`transition-colors duration-[120ms] hover:bg-surface-3`, `t-ui block text-ink-1`, `t-caption block text-ink-4`,
`ml-auto text-ink-5`.

---

## S3 - Endpoints

### 3.1 Existing, reused unchanged

| Method | Path | Role | Query | Response |
|---|---|---|---|---|
| `GET` | `/api/v1/audit/verify` | administrateur | *(none - see F2)* | `{intact: bool, entries: number}` |
| `GET` | `/api/v1/jobs/integrity` | administrateur | - | `{ok, orphans, audit_chain_intact, audit_entries}` |
| `POST` | `/api/v1/jobs/retention` | administrateur | `retention_days`, `dry_run` | flat `RetentionReport`, no envelope |

### 3.2 New - one method, one route (read-only)

**Justification against Constraint 3.** `/settings` promises audit, and a panel that reports *"chain
intact, 14,392 entries"* without being able to show a single entry is half a feature. The rows already
exist in `audit.audit_ledger`; `PgAuditLedger` simply has no reader. Exposing existing rows is access,
not new business logic - the same reasoning that authorised `session_list` (Cookbook 4) and
`analytics_trend` (Cookbook 9). Nothing is mutated: this lands in `SupervisionRepository`, whose
docstring already states *"Read-only; never mutates audit."*

**File:** `apps/business-api/src/business_api/repositories.py`
**Placement:** after `analytics_trend()` if Cookbook 9 is applied, otherwise after `telemetry_timeline()`.
**Existing code modified: none.**

```python
    def audit_entries(self, limit: int = 50, before_seq: int | None = None,
                      event_type: str | None = None) -> dict:
        """Most recent audit ledger entries, newest first. Read-only; keyset paging on seq."""
        from persistence.models.audit import AuditLedgerEntry

        stmt = select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.desc()).limit(limit + 1)
        if before_seq is not None:
            stmt = stmt.where(AuditLedgerEntry.seq < before_seq)
        if event_type:
            stmt = stmt.where(AuditLedgerEntry.event_type == event_type)

        rows = list(self._s.scalars(stmt))
        has_more = len(rows) > limit
        rows = rows[:limit]

        return {
            "entries": [
                {
                    "seq": r.seq,
                    "event_type": r.event_type,
                    "entity_reference": r.entity_reference,
                    "session_id": str(r.session_id) if r.session_id else None,
                    "entry_hash": r.entry_hash,
                    "previous_hash": r.previous_hash,
                    "created_at": r.created_at.isoformat(),
                    "payload": r.payload,
                }
                for r in rows
            ],
            "has_more": has_more,
            "next_before_seq": rows[-1].seq if rows and has_more else None,
        }
```

**File:** `apps/business-api/src/business_api/main.py`
**Placement:** immediately after the `audit_verify` route, before `business_rules`.
**Existing code modified: none.**

```python
@app.get("/api/v1/audit/entries")
def audit_entries(session: DbSession, role: AdministrateurRole, limit: int = 50,
                  before_seq: int | None = None, event_type: str | None = None) -> dict:
    """Browse the append-only audit ledger, newest first (read-only)."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return SupervisionRepository(session).audit_entries(limit, before_seq, event_type)
```

Design notes, each load-bearing:

- **Keyset paging on `seq`, not `OFFSET`.** `seq` is the unique, monotonic chain order; offset paging
  over an append-only table shifts rows under the reader as new entries arrive.
- **`limit + 1` fetch** derives `has_more` without a second `COUNT(*)` over a table that only grows.
- **`created_at.isoformat()`**, matching the Cookbook 8 rule - never ship a pre-formatted timestamp
  (this is precisely the mistake `telemetry_timeline` makes, Cookbook 9 F4).
- **`limit` is clamped 1-200.** Unbounded `limit` on the largest table in the system is a trivial
  resource sink from an authenticated seat.
- **Both hashes are returned** so the operator can eyeball the linkage between adjacent rows.
- `AdministrateurRole`, matching every sibling audit route.

### 3.3 CORS / middleware

**No change.** All traffic goes through the TanStack server proxy (Feature 0). The browser never
contacts `:8108`.

---

## S4 - Frontend implementation plan

### 4.0 File manifest

| Action | Path |
|---|---|
| NEW | `src/lib/api/audit.server.ts` |
| NEW | `src/lib/nexus/audit-view.ts` |
| NEW | `src/components/nexus/retention-panel.tsx` |
| MOD | `src/lib/nexus/query-keys.ts` (+`auditKeys`) |
| MOD | `src/lib/nexus/data.ts` (remove `SETTINGS_SECTIONS` - **grep + confirm first**, S8.3) |
| REWRITE | `src/routes/settings.tsx` |

No new npm dependencies. No new tokens. **`status.ts` untouched. `nav.ts` untouched.
`routeTree.gen.ts` untouched. `primitives.tsx` untouched. `blocks.tsx` untouched.**

### 4.1 `src/lib/api/audit.server.ts` (new)

```ts
import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware } from "@/lib/api/middleware";
import { inputValidator } from "@/lib/api/validation";

export type AuditVerification = { intact: boolean; entries: number };

export type IntegrityReport = {
  ok: boolean;
  orphans: Record<string, number>;
  audit_chain_intact: boolean;
  audit_entries: number;
};

export type AuditEntry = {
  seq: number;
  event_type: string;
  entity_reference: string | null;
  session_id: string | null;
  entry_hash: string;
  previous_hash: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export type AuditEntryPage = {
  entries: AuditEntry[];
  has_more: boolean;
  next_before_seq: number | null;
};

export type RetentionReport = {
  cutoff: string;
  sessions_matched: number;
  turns_anonymized: number;
  dry_run: boolean;
};

/** Whole-chain SHA-256 recomputation. Expensive and unbounded - never auto-run. See F3. */
export const verifyAuditChain = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async ({ context }) =>
    businessApi<AuditVerification>("/api/v1/audit/verify", { role: context.session.role }),
  );

/** Also recomputes the whole chain internally, plus four COUNT(*)s. See F5. */
export const runIntegrityReport = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async ({ context }) =>
    businessApi<IntegrityReport>("/api/v1/jobs/integrity", { role: context.session.role }),
  );

export const listAuditEntries = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { beforeSeq?: number; eventType?: string };
    return {
      beforeSeq: typeof input.beforeSeq === "number" ? input.beforeSeq : undefined,
      eventType: input.eventType?.trim() || undefined,
    };
  })
  .handler(async ({ data, context }) =>
    businessApi<AuditEntryPage>("/api/v1/audit/entries", {
      query: {
        limit: 50,
        ...(data.beforeSeq === undefined ? {} : { before_seq: data.beforeSeq }),
        ...(data.eventType === undefined ? {} : { event_type: data.eventType }),
      },
      role: context.session.role,
    }),
  );

/**
 * Retention. `retention_days` and `dry_run` are QUERY parameters - the backend route has no
 * body model, so a JSON body is silently ignored and the defaults (90, dry_run=true) apply. F8.
 */
export const runRetention = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { retentionDays?: unknown; dryRun?: unknown };
    const days = Number(input.retentionDays);
    if (!Number.isInteger(days) || days < 30 || days > 3650) {
      throw new Error("Retention window must be a whole number between 30 and 3650 days.");
    }
    return { retentionDays: days, dryRun: input.dryRun !== false };
  })
  .handler(async ({ data, context }) =>
    businessApi<RetentionReport>("/api/v1/jobs/retention", {
      method: "POST",
      query: { retention_days: data.retentionDays, dry_run: data.dryRun },
      role: context.session.role,
    }),
  );
```

Four deliberate choices:

- **`verifyAuditChain` and `runIntegrityReport` are `method: "POST"` server functions even though the
  backend routes are `GET`.** The transport is a React Start concern, and the reason is concrete: the
  global QueryClient sets **`refetchOnWindowFocus: true`**. Modelled as queries, these would recompute
  the entire SHA-256 chain every single time the operator alt-tabs back to the browser. They are
  modelled as mutations and invoked only by an explicit click.
- **`dryRun: input.dryRun !== false`** - the default is `true` and the *only* way to get a real purge
  is to pass the literal boolean `false`. `undefined`, `null`, `0`, `"false"` all resolve to a dry run.
  For an irreversible operation the failure mode must point at safety.
- **`retentionDays` is validated to 30-3650 and throws rather than clamping.** Silently clamping a
  destructive parameter would let an operator ask for 0 and receive 30 without noticing. This is the
  frontend half of S8.1; it is a usability guard, **not** a security control.
- **Query params, never a body** - F8.

### 4.2 `src/lib/nexus/audit-view.ts` (new - pure)

```ts
import type { AuditEntry, IntegrityReport } from "@/lib/api/audit.server";

/** "billing.accounts->crm.customers" -> "billing.accounts -> crm.customers" */
export function orphanLabel(key: string): string {
  return key.replace("->", " \u2192 ");
}

/**
 * Pass/fail as a canonical status key. Reuses the Cookbook 8 mapping (succeeded -> resolved),
 * so a passing check reads the same across the console. `resolved` and `failed` both exist in
 * status.ts; no new status key is introduced.
 */
export function checkStatusKey(passed: boolean): "resolved" | "failed" {
  return passed ? "resolved" : "failed";
}

export function totalOrphans(report: IntegrityReport): number {
  return Object.values(report.orphans).reduce((sum, n) => sum + n, 0);
}

/** First 12 hex characters, matching the backend's own log format (`hash=%s`, [:12]). */
export function shortHash(hash: string): string {
  return hash.slice(0, 12);
}

/** Chain linkage: does this row's previous_hash match the next-older row's entry_hash? */
export function isLinked(newer: AuditEntry, older: AuditEntry | undefined): boolean {
  return older === undefined || newer.previous_hash === older.entry_hash;
}

export function eventLabel(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

/** ISO instant -> "2026-08-03 14:32" in the browser's locale-independent form. */
export function formatInstant(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** The sentence the operator must read before an irreversible purge. */
export function blastRadius(sessionsMatched: number, cutoffIso: string): string {
  const when = formatInstant(cutoffIso);
  if (sessionsMatched === 0) return `No sessions started before ${when}. Nothing would be purged.`;
  return (
    `${sessionsMatched.toLocaleString("en-US")} session(s) started before ${when}. ` +
    `Their transcripts will be overwritten with "[purged]" and their audio recordings deleted. ` +
    `This cannot be undone.`
  );
}
```

`formatInstant` uses `new Date(iso)` deliberately here, unlike Cookbook 9's `dayLabel`. The distinction
matters: **these are full ISO-8601 instants with an offset** (`created_at.isoformat()` on a tz-aware
column), which `Date` parses unambiguously. Cookbook 9's ban applied to **date-only** strings, which
`Date` parses as UTC midnight and then shifts. Same codebase, two different inputs, two different
correct answers.

### 4.3 `src/lib/nexus/query-keys.ts` (modified)

```ts
export const auditKeys = {
  all: ["audit"] as const,
  entries: (eventType?: string) => [...auditKeys.all, "entries", eventType ?? ""] as const,
};
```

Only the browse list is a query. Verify, integrity and retention are mutations and hold no cache key.

### 4.4 `src/components/nexus/retention-panel.tsx` (new)

The two-phase guard from S0, isolated in its own component because it is the only stateful piece.

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Card, CardHeader, Button, TextField, Token } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { runRetention, type RetentionReport } from "@/lib/api/audit.server";
import { blastRadius, formatInstant } from "@/lib/nexus/audit-view";
import { errorMessage } from "@/lib/api/errors";

export function RetentionPanel() {
  const [days, setDays] = useState("90");
  const [preview, setPreview] = useState<RetentionReport | null>(null);
  const [previewedDays, setPreviewedDays] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<RetentionReport | null>(null);

  // Any change to the window invalidates the dry run and re-locks the purge.
  function changeDays(next: string) {
    setDays(next);
    setPreview(null);
    setPreviewedDays(null);
    setResult(null);
  }

  const dryRun = useMutation({
    mutationFn: () => runRetention({ data: { retentionDays: Number(days), dryRun: true } }),
    onSuccess: (report) => {
      setPreview(report);
      setPreviewedDays(days);
      setResult(null);
    },
  });

  const purge = useMutation({
    mutationFn: () => runRetention({ data: { retentionDays: Number(days), dryRun: false } }),
    onSuccess: (report) => {
      setResult(report);
      setPreview(null);
      setPreviewedDays(null);
      setConfirmOpen(false);
      setTyped("");
    },
  });

  const previewValid = preview !== null && previewedDays === days;
  const expected = String(preview?.sessions_matched ?? "");
  const canPurge = previewValid && preview.sessions_matched > 0;

  return (
    <Card>
      <CardHeader
        title="Data Retention"
        subtitle="Anonymize transcripts and delete audio recordings older than the retention window."
      />

      <div className="mt-sp-6 flex items-end gap-sp-5">
        <TextField
          label="Retention window (days)"
          value={days}
          onChange={(e) => changeDays(e.target.value)}
          inputMode="numeric"
        />
        <Button onClick={() => dryRun.mutate()} disabled={dryRun.isPending}>
          {dryRun.isPending ? "Checking..." : "Preview"}
        </Button>
        <Button onClick={() => setConfirmOpen(true)} disabled={!canPurge || purge.isPending}>
          Purge permanently
        </Button>
      </div>

      {dryRun.isError ? (
        <div className="mt-sp-5"><InlineError message={errorMessage(dryRun.error)} /></div>
      ) : null}
      {purge.isError ? (
        <div className="mt-sp-5"><InlineError message={errorMessage(purge.error)} /></div>
      ) : null}

      {previewValid ? (
        <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-ui text-ink-1">
            {blastRadius(preview.sessions_matched, preview.cutoff)}
          </p>
          <p className="t-caption mt-sp-3 text-ink-4">
            Preview only. The number of transcript turns affected is not reported until the purge runs.
          </p>
        </div>
      ) : null}

      {result ? (
        <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-ui text-ink-1">
            Purge complete. {result.sessions_matched.toLocaleString("en-US")} session(s) processed,{" "}
            {result.turns_anonymized.toLocaleString("en-US")} transcript turn(s) anonymized.
          </p>
          <p className="t-caption mt-sp-3 text-ink-4">
            Cutoff {formatInstant(result.cutoff)}. Audio deletion failures are not reported by the job.
          </p>
        </div>
      ) : null}

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title="Confirm permanent purge">
        <div className="flex items-start gap-sp-5">
          <AlertTriangle size={16} strokeWidth={1.5} aria-hidden="true" className="mt-sp-2 text-ink-3" />
          <p className="t-ui text-ink-1">
            {preview ? blastRadius(preview.sessions_matched, preview.cutoff) : ""}
          </p>
        </div>
        <p className="t-caption mt-sp-5 text-ink-4">
          Type <Token>{expected}</Token> to confirm.
        </p>
        <div className="mt-sp-5">
          <TextField
            label="Session count"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            inputMode="numeric"
          />
        </div>
        <div className="mt-sp-6 flex justify-end gap-sp-5">
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            onClick={() => purge.mutate()}
            disabled={typed.trim() !== expected || purge.isPending}
          >
            {purge.isPending ? "Purging..." : "Purge permanently"}
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
```

Why each guard exists:

- **`previewValid = preview !== null && previewedDays === days`.** Previewing 365 days and then editing
  the field to 30 must not leave a stale, reassuring preview above an armed purge button. Editing the
  window resets everything.
- **`canPurge` requires `sessions_matched > 0`.** A no-op purge still writes an audit entry and still
  commits; there is no reason to allow it.
- **Typing the exact session count**, not the word "DELETE". The operator has to look at the blast
  radius to type it, which is the entire point.
- **The dry-run caption states plainly that the turn count is unknown** - F6. The panel never shows
  `turns_anonymized` from a dry run, because that zero is an artefact of the `if not dry_run` guard.
- **The result caption states that audio failures are not reported** - F7. The operator should not read
  a clean report as proof the blobs are gone.
- `Modal` is Feature 1's, which portals to `document.body` - mandatory inside `PageSection`, whose
  `.rise` transform creates a containing block and would otherwise clip the scrim.

### 4.5 `src/routes/settings.tsx` (rewritten)

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Card, CardHeader, Button, StatusChip, Token, EmptyState, TableShell, Th, Td } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableSkeleton, ErrorState, InlineError, TableErrorRow } from "@/components/nexus/states";
import { RetentionPanel } from "@/components/nexus/retention-panel";
import { verifyAuditChain, runIntegrityReport, listAuditEntries } from "@/lib/api/audit.server";
import { auditKeys } from "@/lib/nexus/query-keys";
import {
  checkStatusKey, orphanLabel, totalOrphans, shortHash, eventLabel, formatInstant, isLinked,
} from "@/lib/nexus/audit-view";
import { getSession } from "@/lib/api/session";
import { hasRank } from "@/lib/nexus/roles";
import { formatInteger } from "@/lib/nexus/format";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings \u2014 Nexus" },
      { name: "description", content: "Audit chain, referential integrity and data retention." },
      { property: "og:title", content: "Settings \u2014 Nexus" },
      { property: "og:description", content: "Administrative operations for the platform." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const session = useQuery({ queryKey: ["session"], queryFn: () => getSession() });
  const isAdmin = session.data ? hasRank(session.data.role, "administrateur") : false;

  if (session.isPending) return <PageSection><TableSkeleton rows={3} cols={2} /></PageSection>;

  if (!isAdmin) {
    return (
      <PageSection>
        <Card>
          <EmptyState
            title="Administrator access required"
            description="Audit verification, integrity checks and data retention are restricted to administrators."
          />
        </Card>
      </PageSection>
    );
  }

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-2">
        <AuditChainPanel />
        <IntegrityPanel />
      </PageSection>

      <PageSection>
        <RetentionPanel />
      </PageSection>

      <PageSection>
        <AuditLedgerTable />
      </PageSection>
    </>
  );
}

function AuditChainPanel() {
  const verify = useMutation({ mutationFn: () => verifyAuditChain() });

  return (
    <Card>
      <CardHeader
        title="Audit Chain"
        subtitle="Recompute every hash in the ledger and confirm the chain is unbroken."
        action={
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
            {verify.isPending ? "Verifying..." : "Verify chain"}
          </Button>
        }
      />
      <div className="mt-sp-6">
        {verify.isError ? (
          <InlineError message={errorMessage(verify.error)} />
        ) : verify.data ? (
          <div className="flex items-center gap-sp-5">
            <StatusChip status={checkStatusKey(verify.data.intact)} />
            <span className="t-ui text-ink-1">
              {verify.data.intact ? "Chain intact" : "Chain broken \u2014 investigate immediately"}
            </span>
            <span className="t-label ml-auto text-ink-3">
              {formatInteger(verify.data.entries)} entries
            </span>
          </div>
        ) : (
          <p className="t-caption text-ink-4">
            Not run yet. Verification reads the whole ledger, so it runs only when you ask for it.
          </p>
        )}
      </div>
    </Card>
  );
}

function IntegrityPanel() {
  const integrity = useMutation({ mutationFn: () => runIntegrityReport() });

  return (
    <Card>
      <CardHeader
        title="Referential Integrity"
        subtitle="Cross-domain orphan checks plus the audit chain."
        action={
          <Button onClick={() => integrity.mutate()} disabled={integrity.isPending}>
            {integrity.isPending ? "Running..." : "Run check"}
          </Button>
        }
      />
      <div className="mt-sp-6">
        {integrity.isError ? (
          <InlineError message={errorMessage(integrity.error)} />
        ) : integrity.data ? (
          <>
            <div className="flex items-center gap-sp-5">
              <StatusChip status={checkStatusKey(integrity.data.ok)} />
              <span className="t-ui text-ink-1">
                {integrity.data.ok
                  ? "No orphans, chain intact"
                  : `${formatInteger(totalOrphans(integrity.data))} orphaned row(s)`}
              </span>
            </div>
            <ul className="mt-sp-5">
              {Object.entries(integrity.data.orphans).map(([key, count]) => (
                <li key={key} className="flex items-center gap-sp-5 border-t border-stroke-subtle py-sp-4">
                  <span className="t-caption truncate text-ink-3">{orphanLabel(key)}</span>
                  <Token className="ml-auto">{formatInteger(count)}</Token>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="t-caption text-ink-4">Not run yet.</p>
        )}
      </div>
    </Card>
  );
}

function AuditLedgerTable() {
  const [eventType, setEventType] = useState("");
  const entries = useQuery({
    queryKey: auditKeys.entries(eventType),
    queryFn: () => listAuditEntries({ data: { eventType: eventType || undefined } }),
  });

  return (
    <Card padded={false}>
      <div className="p-sp-7">
        <CardHeader title="Audit Ledger" subtitle="The 50 most recent entries, newest first." />
      </div>
      <TableShell
        head={
          <tr>
            <Th>Seq</Th>
            <Th>Event</Th>
            <Th>Reference</Th>
            <Th>Hash</Th>
            <Th>When</Th>
          </tr>
        }
      >
        {entries.isPending ? (
          <TableSkeleton rows={6} cols={5} />
        ) : entries.isError ? (
          <TableErrorRow colSpan={5} message={errorMessage(entries.error)} onRetry={() => entries.refetch()} />
        ) : entries.data.entries.length === 0 ? (
          <tr>
            <Td colSpan={5}>
              <EmptyState title="No audit entries" description="Nothing has been recorded yet." />
            </Td>
          </tr>
        ) : (
          entries.data.entries.map((entry, index) => {
            const older = entries.data.entries[index + 1];
            const linked = isLinked(entry, older);
            return (
              <tr key={entry.seq}>
                <Td><Token>{entry.seq}</Token></Td>
                <Td>{eventLabel(entry.event_type)}</Td>
                <Td>{entry.entity_reference ?? "\u2014"}</Td>
                <Td>
                  <Token>{shortHash(entry.entry_hash)}</Token>
                  {linked ? null : (
                    <span className="t-caption ml-sp-4 text-ink-3">link mismatch</span>
                  )}
                </Td>
                <Td>{formatInstant(entry.created_at)}</Td>
              </tr>
            );
          })
        )}
      </TableShell>
    </Card>
  );
}
```

Three call-site cautions carried forward from earlier features:

- **`Td` may not forward `colSpan`** (noted since Feature 0). Verify before relying on the empty row;
  Cookbook 4 hit this.
- **`TextField`'s `onChange` signature** - Feature 0 added it; confirm it passes the event rather than
  the raw string before wiring `e.target.value`.
- **`isLinked` is a local display hint only.** It compares adjacent rows *in the fetched page*. It is
  **not** a verification - it does not recompute any hash, and page boundaries will always show the
  oldest row as linked because there is nothing below it to compare. The authoritative answer comes
  from the Verify button. The label says "link mismatch", never "tampered".

### 4.6 `src/lib/nexus/data.ts` (modified)

Remove `SETTINGS_SECTIONS`. **Grep first:**

```bash
grep -rn "SETTINGS_SECTIONS" Frontend/admin_dashboard/src
```

Expect a single hit in `settings.tsx`. See S8.3 before deleting - those rows name features
(members, roles, API keys) that may matter to you even though they have no backend.

---

## S5 - Findings

**F1 - `retention_days` has no floor; `retention_days=0&dry_run=false` destroys everything.**
`cutoff_date(0)` is `now`, so `start_time < cutoff` matches every session. Transcripts are overwritten
in place and audio blobs are deleted from object storage. No undo. Reachable by any `administrateur`
with a URL bar, entirely bypassing the UI guard. **Headline. Backend fix drafted in S8.1, not shipped.**

**F2 - `/api/v1/audit/verify` accepts `from_seq`/`to_seq` and silently ignores them.** The docstring
concedes *"range is a later refinement"*. A caller passing a range receives a whole-chain result with
nothing marking the range as dropped - a verification that appears scoped but is not, which is exactly
the wrong way for an audit tool to mislead. **The UI exposes no range control.**

**F3 - `verify()` is unbounded.** It materialises every ledger row and recomputes every SHA-256, with
no limit and no early exit. Cost grows forever. Combined with the global `refetchOnWindowFocus: true`,
modelling it as a query would re-run the whole chain on every tab switch. Modelled as a mutation.

**F4 - There is no way to read audit entries.** `PgAuditLedger` exposes only `append`, `verify`,
`count`. The `/settings` page promises "audit" and the platform could not show a single row. Resolved
by the new read-only endpoint (S3.2).

**F5 - The chain is verified twice if both buttons are pressed.** `run_integrity` calls
`ledger.verify()` internally, so `/jobs/integrity` already includes everything `/audit/verify` returns.
The two panels are kept separate because the integrity job additionally runs four `COUNT(*)`s and an
operator often wants only the cheap answer - but they are never fired together.

**F6 - A dry run cannot report the turn count.** `turns_anonymized` is assigned inside
`if not dry_run and matched:`, so a preview always returns `0` - not because no turns match, but
because it never counts them. **The dry run under-reports the blast radius.** The panel shows only
`sessions_matched` and says so explicitly.

**F7 - Audio deletion is irreversible, non-transactional, and silent on failure.**
`with suppress(Exception): store.delete(url)` runs *before* `session.commit()`. Blobs can be destroyed
and the transaction can still fail, leaving rows pointing at deleted objects. Failures are swallowed
and absent from `RetentionReport`. The result caption says so rather than implying a clean sweep.

**F8 - `retention_days` and `dry_run` are query parameters.** The route has no Pydantic body model. A
JSON body is silently ignored and the defaults apply. The safe direction (an ignored body yields
`dry_run=True`), but a `retention_days` sent in a body would silently become 90.

**F9 - `POST /api/v1/jobs/retention` returns `.__dict__`, flat, no envelope.** Second occurrence of
this convention break after `/api/v1/kpis` (Cookbook 9 G2). Verified in `main.py`, not assumed.

**F10 - Chain order is `seq`, not `created_at` or `id`.** `append()` reads the last row by
`seq.desc()`. Ordering a display by `created_at` could show rows out of chain order and make an intact
chain look broken. Both the new endpoint and the table order by `seq`.

**F11 - Chip trap, eighth recurrence - avoided without touching `status.ts`.** Integrity results are
booleans, not status strings, so `StatusChip` would receive `true`/`false` and `STATUS[status]` would
be `undefined`, rendering **nothing at all** - a pass/fail panel showing neither. Mapped through
`checkStatusKey` to `resolved` / `failed`, reusing Cookbook 8's `succeeded -> resolved` precedent.
**Tenth consecutive cookbook with zero `status.ts` changes.**

**F12 - Audit payloads may contain sensitive data.** `payload` is free-form `JSONB`; the policy engine
writes `inputs_snapshot`-shaped content, and `PiiTokenMap` exists precisely because raw PII is
tokenised elsewhere. I have **not** audited every writer. The endpoint is `administrateur`-only and the
table **deliberately does not render `payload`** - only `seq`, event, reference, hash and time. See
S8.4 before adding a payload viewer.

**F13 - `/settings` is currently inert.** Every row is a `<button>` with no handler and a chevron
promising navigation that does not exist. Following the Feature 5 precedent ("New ticket" removed, not
disabled), the inert list is replaced rather than left in place.

**F14 - `run_retention` commits internally.** Every other mutation lets `main.py` own the commit. Not a
defect, but it means the route cannot participate in a larger transaction, and a caller cannot roll the
purge back after the fact.

---

## S6 - Validation checklist

**Backend**

- [ ] `ledger.py`, `integrity.py`, `retention.py`, `audit.py` **byte-identical** to their v79 SHAs.
- [ ] All 34 existing routes byte-identical; only `audit_entries` added.
- [ ] `GET /api/v1/audit/entries` returns 200 for `limit=1` and `limit=200`, 400 for `0` and `201`.
- [ ] Returns 403 for `conseiller` and `superviseur`, 200 for `administrateur`.
- [ ] `entries` are ordered by `seq` **descending**; `seq` values strictly decrease.
- [ ] `before_seq` paging returns no overlap and no gap against the first page.
- [ ] `event_type="data_retention"` filters correctly after a real purge.
- [ ] `created_at` is a full ISO-8601 instant with offset, never a pre-formatted string.
- [ ] Empty ledger returns `{entries: [], has_more: false, next_before_seq: null}`, not an error.

**Frontend**

- [ ] `tsc --noEmit` clean.
- [ ] `lint` returns exactly the **36-problem baseline** (28 prettier errors + 8 warnings).
- [ ] `build` exits 0.
- [ ] `grep -rn "SETTINGS_SECTIONS" src` returns **zero** hits after the rewrite.
- [ ] **Zero** direct browser requests to `:8108`.
- [ ] No new npm dependency; `package.json` untouched.
- [ ] `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/settings.tsx src/components/nexus/retention-panel.tsx src/lib/nexus/audit-view.ts` -> no hits.
- [ ] `status.ts`, `nav.ts`, `routeTree.gen.ts`, `primitives.tsx`, `blocks.tsx` all untouched.
- [ ] Signed in as `superviseur` -> permission notice, and **no** audit request is issued at all.
- [ ] Signed in as `administrateur` -> all three panels render.
- [ ] Verify and Run check fire **only** on click; alt-tabbing away and back issues **no** request.
- [ ] Backend stopped -> each panel shows its own inline error; the page does not blank.

**Retention guard - test every one of these**

- [ ] Purge button is disabled before any preview.
- [ ] Preview 90 days, then edit the field to 91 -> preview clears **and** purge re-locks.
- [ ] Preview returning `sessions_matched = 0` -> purge stays disabled.
- [ ] Confirm button stays disabled until the typed count matches exactly; `" 12 "` trims and passes, `"12x"` does not.
- [ ] `retentionDays = 0`, `-1`, `29`, `3651`, `"abc"`, `""` -> validator throws, **no request is sent**.
- [ ] Network tab: preview sends `dry_run=true`; purge sends `dry_run=false`; both as **query parameters**, no JSON body.
- [ ] Dry-run result never displays a turn count.
- [ ] After a real purge, a new entry with `event_type="data_retention"` appears in the ledger table.
- [ ] **On a disposable database only:** run a real purge and confirm `Turn.transcript_masked` is `"[purged]"` and `audio_record_url` is NULL for matched sessions.

---

## S7 - Dependencies and ordering

Depends on **Feature 0** (applied - `businessApi`, `authedMiddleware`, `inputValidator`, `getSession`,
`hasRank`, `TextField`, states) and **Feature 1** (applied - `Modal`, which portals to `document.body`).

Independent of Cookbooks 3-9. If Cookbook 9 is applied first, place `audit_entries` after
`analytics_trend`; otherwise after `telemetry_timeline`. Either order works.

---

## S8 - Open questions

**S8.1 - Add a floor to `retention_days`? (STRONGLY RECOMMENDED)** This is the one change I will not
make unilaterally, because it modifies existing backend behaviour and Constraint 2 is explicit. But F1
is a genuine data-loss hazard, and the UI guard protects nobody using `curl`. The minimal fix touches
only the route, never `run_retention`:

```python
@app.post("/api/v1/jobs/retention")
def retention(session: DbSession, role: AdministrateurRole,
              retention_days: int = 90, dry_run: bool = True) -> dict:
    if retention_days < 30:
        raise HTTPException(status_code=400, detail="retention_days must be at least 30")
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__
```

It rejects input that is currently accepted, so it is a behaviour change and it is your call. **Is 30
days the right floor for your jurisdiction and contracts?** Say the word and I will ship it.

**S8.2 - Should the retention job be schedulable?** The module docstring says the blob purge is done
*"by the same scheduler at integration"*, implying a scheduler that I have not found in the repository.
Today retention only ever runs when a human clicks. If a scheduler exists somewhere I have not read,
tell me - it changes whether this panel is the primary trigger or a manual override.

**S8.3 - What were the `/settings` rows meant to be?** The mock lists sections and the `head`
description names *"members, roles, API keys"*. **None of those have any backend.** There is no user
table for dashboard accounts (Feature 0 authenticates against `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars),
no role assignment surface beyond the `X-Role` header, and no API key management anywhere. I removed
the inert rows rather than leaving dead chevrons. **Confirm that is what you want, and tell me if any
of those three should become a real feature** - each needs backend business logic, so each is a flag
under Constraint 3, not something I will build.

**S8.4 - Should audit payloads be viewable?** Currently hidden (F12). A payload viewer is genuinely
useful for investigating a broken chain, but I have not audited every `append()` caller for PII. If you
want it, I would add it as an expandable row behind an explicit "Show payload" action - and I would
want to read every writer first.

**S8.5 - Should a broken chain raise an alarm?** Right now a break is visible only if someone clicks
Verify. Given the chain is the tamper-evidence mechanism for the whole platform, a silent break is the
worst possible failure. Notification would need backend work (there is a `notification-service` on
8106), so it is flagged, not built.

**S8.6 - Paging the audit ledger.** The endpoint supports keyset paging; the UI shows only the first 50
with no "Load more". Deliberate - no other table in the applied set pages yet, and Cookbook 8 S8.5
raises the same question. Worth deciding once, consistently, across `/decisions`, `/calls` and here.

**S8.7 - `from_seq`/`to_seq` (F2): implement or remove?** Leaving accepted-but-ignored parameters on an
audit endpoint is a trap for any future caller. Either implement ranged verification or delete the
parameters. Both are backend changes to existing code, so both need your approval.

---

## S9 - Flags raised outside this feature's scope

**S9.1 - `session_detail`'s unguarded `float(call.max_frustration_score)` remains unfixed.** Now
four-way relevant: `/calls` (C4), `/decisions` (C8), and any drill-through from the audit ledger's
`session_id`. `kpis()` and `telemetry_timeline()` both guard the same column correctly - the fix is one
`or 0`.

**S9.2 - Retention destroys the data `/calls` displays.** Cookbook 4's transcript view reads
`Turn.transcript_masked`; after a purge those rows read `"[purged]"`. That is correct behaviour, but
`/calls` has no notion of it and will render the literal string as if it were speech. Worth a small
follow-up so purged transcripts are presented as purged rather than as content.

**S9.3 - The admin dashboard has no real user store.** Feature 0's stop-gap (env-var credentials,
single account) is still the authentication model, and S8.3 shows the mock expected members and roles.
This remains the largest unresolved gap in the admin console, and it is backend business logic.
