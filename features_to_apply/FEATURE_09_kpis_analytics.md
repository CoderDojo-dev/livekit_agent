# Cookbook 9 — KPIs & Analytics (`/overview`, `/analytics`)

**Branch of record:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Working branch:** `version_80`
**Scope:** admin dashboard only. Client/customer dashboard untouched.
**Backend changes:** +1 repository method, +1 route. **Zero modifications to existing backend logic.**

---

## §0 — The decision that shapes this cookbook

`SupervisionRepository.system_overview()` returns an eleven-service health matrix. Every entry is a
Python literal:

```python
services = [
    {"name": "context-service", "port": 8101, "domain": "Customer 360 & Auth", "status": "online"},
    {"name": "knowledge-service", "port": 8102, "domain": "Semantic RAG & Documents", "status": "online"},
    ...
    {"name": "messaging-gateway", "port": 8203, "domain": "SMS/Email Gateway MCP", "status": "online"},
]
```

There is no probe, no timeout, no socket, no `httpx` call. **The string `"online"` is hardcoded
eleven times.** The route docstring says *"Real-time system overview: database counts + service
status matrix"* — the counts are real; the matrix is not.

Rendered faithfully, this page would display **eleven green services during a total outage.** That is
strictly worse than displaying nothing, because it manufactures confidence precisely when an operator
is looking for a reason to lose it. A blank panel prompts investigation; a false green panel ends it.

**Decision: the `status` field is never rendered.** The service list still ships — as a *service
inventory* (name, port, domain), which is genuinely useful and genuinely true — with no status chip,
no presence dot, and no colour encoding. Making it real means fanning out health probes to eleven
services, which is new business logic, so by Constraint 3 it is **flagged, not built** (§8.1).

This is the same rule Cookbook 5 established (never surface a value that an upstream source will
contradict) and Cookbook 7 generalised (never expose a number the system does not actually enforce),
now in its sharpest form: **never render a status the backend did not measure.**

The second shaping fact is smaller but decides the whole layout:

> `StatCard.delta` and `HeroStat.delta` are **`number`, not `number | undefined`**, and **no endpoint
> in the backend returns a period comparison.**

`kpis()` is unconditionally cumulative — `select(func.count()).select_from(CallSession)` with no
`WHERE` on time. The overview mock is built almost entirely out of deltas and week-over-week series.
So either every card fabricates a trend, or the primitive learns to render without one. See §4.3.

---

## §1 — Feature name & scope

**Feature 9 — KPIs & Analytics.**

Two routes, both currently mock-only, both currently rendering **byte-identical data**:

| Route | Mock imports | Distinct content |
|---|---|---|
| `/overview` | `OVERVIEW_STATS`, `CALL_VOLUME_SERIES`, `RESOLUTION_SERIES`, `HERO_SPARKLINE`, `BILLING_ACTIVITY`, `ADVISOR_TEAM` | + billing + team panels |
| `/analytics` | `OVERVIEW_STATS`, `CALL_VOLUME_SERIES`, `RESOLUTION_SERIES`, `HERO_SPARKLINE` | **strict subset of `/overview`** |

`/analytics` is a proper subset of `/overview`. Wiring both to the same endpoints would ship two live
pages that are still the same page. **Decision (§4.1): give each a distinct, backed purpose.**

- **`/overview` — current state.** Cumulative platform totals, all-time KPIs, verdict mix, who is on
  the floor right now, service inventory. No trends, because none exist for cumulative figures.
- **`/analytics` — trends.** A windowed comparison (7 / 14 / 30 days) of the *same* KPI definitions
  against the preceding equal-length window, plus a daily volume line. This is where deltas belong,
  and it is the only place they can be honest.

Out of scope: the client dashboard; `/settings`; `/rules`; `/conversations`.

---

## §2 — Backend reference (exact names and paths)

### 2.1 `apps/business-api/src/business_api/kpis.py` (`fb5afcd8`) — FULLY CAPTURED

```python
"""KPI math (Blueprint section 16.1) - pure, unit-testable."""

@dataclass
class Kpis:
    total_sessions: int
    resolved: int
    escalated: int
    containment_rate: float
    escalation_rate: float
    avg_frustration: float

def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0

def compute_kpis(total_sessions, resolved, escalated, avg_frustration) -> Kpis:
    return Kpis(
        total_sessions=total_sessions,
        resolved=resolved,
        escalated=escalated,
        containment_rate=_ratio(resolved, total_sessions),
        escalation_rate=_ratio(escalated, total_sessions),
        avg_frustration=round(float(avg_frustration or 0), 2),
    )
```

Four facts the frontend depends on:

1. `containment_rate` / `escalation_rate` are **ratios in `0.0…1.0`**, rounded to 4 dp — *not*
   percentages. `0.8421`, not `84.21`.
2. `_ratio` returns **`0.0` on an empty denominator**, so a fresh database yields `0.0`, not a crash
   and not `null`. An empty estate and a 0 %-containment estate are indistinguishable in this field —
   disambiguate with `total_sessions` (G3).
3. `avg_frustration` is rounded to 2 dp and `float(avg_frustration or 0)` absorbs `None`.
4. The module is **pure** — no session, no I/O. It is therefore safe to reuse verbatim for a windowed
   bundle, which is what §3.2 does. No modification required.

### 2.2 `repositories.py` (`0f9acd1f`) — the three methods in play

```python
def kpis(self) -> Kpis:
    total = self._s.scalar(select(func.count()).select_from(CallSession)) or 0
    resolved = self._s.scalar(select(func.count()).select_from(CallSession)
        .where(CallSession.final_disposition == "resolved")) or 0
    escalated = self._s.scalar(select(func.count()).select_from(CallSession)
        .where(CallSession.final_disposition == "escalated")) or 0
    avg_frustration = self._s.scalar(
        select(func.coalesce(func.avg(CallSession.max_frustration_score), 0)))
    return compute_kpis(total, resolved, escalated, avg_frustration)
```

Note `func.coalesce(func.avg(...), 0)` — **this is the guarded sibling of the `session_detail` bug.**
The same nullable column `max_frustration_score` is read safely here and unsafely there
(`float(call.max_frustration_score)`, no coalesce → the 500 documented in Cookbook 4 §8.7 and
Cookbook 8 §8.6). Feature 9 therefore does **not** inherit that fault: nothing on these two pages
calls `session_detail`.

`system_overview()` returns `{"metrics": {...7 real counts...}, "services": [...11 literals...]}`.
The metrics are honest `SELECT COUNT(*)`s over `CallSession`, `Turn`, `PolicyVerdict`,
`ActionLedger`, `AuditLedgerEntry`, `Customer`, `EscalationCase`.

`telemetry_timeline()` returns `{"timeline": [...], "verdict_distribution": {...}}`:

```python
timeline_points.append({
    "timestamp": s.created_at.strftime("%H:%M:%S") if s.created_at else "00:00:00",
    "duration": s.duration_seconds or 0,
    "frustration": float(s.max_frustration_score or 0.0),
    "disposition": s.final_disposition or "unknown",
})
```

`verdict_distribution` counts `AUTHORIZED` / `REFUSED` / `ESCALATE` over the **last 100 verdicts** via
`v.verdict.upper()`. Real, cheap, and the only verdict aggregate the backend offers.

### 2.3 `main.py` (`ff52daff`) — the three routes, verified verbatim

```python
@app.get("/api/v1/kpis")
def kpis(session: DbSession, role: SuperviseurRole) -> dict:
    return SupervisionRepository(session).kpis().__dict__

@app.get("/api/v1/system/overview")
def system_overview(session: DbSession, role: SuperviseurRole) -> dict:
    return SupervisionRepository(session).system_overview()

@app.get("/api/v1/telemetry/timeline")
def telemetry_timeline(session: DbSession, role: SuperviseurRole) -> dict:
    return SupervisionRepository(session).telemetry_timeline()
```

**`.__dict__` on the dataclass** — I verified this rather than assuming a `{"kpis": …}` envelope. The
response is the flat bundle, **unwrapped**:

```json
{ "total_sessions": 0, "resolved": 0, "escalated": 0,
  "containment_rate": 0.0, "escalation_rate": 0.0, "avg_frustration": 0.0 }
```

This breaks the envelope convention every other list route follows (`{"advisors": …}`,
`{"verdicts": …}`, `{"actions": …}`, `{"rules": …}`). Do not write `data.kpis` (G2).

All three are **`SuperviseurRole`** — rank 2. Reachable by `superviseur` and `administrateur`, not by
`conseiller`.

---

## §3 — Endpoints

### 3.1 Existing, reused unchanged

| Method | Path | Role | Response | Used by |
|---|---|---|---|---|
| `GET` | `/api/v1/kpis` | superviseur | flat `Kpis` dict (no envelope) | `/overview` |
| `GET` | `/api/v1/system/overview` | superviseur | `{metrics, services}` | `/overview` |
| `GET` | `/api/v1/telemetry/timeline` | superviseur | `{timeline, verdict_distribution}` | `/overview` |
| `GET` | `/api/v1/advisors?include_inactive=false` | superviseur | `{advisors: [...]}` | `/overview` team panel |

The advisors route is reused **exactly as Feature 1 wired it** — same server function, same query key,
same `advisor-view.ts` status mapping. Do not re-derive the mapping here (G6).

### 3.2 New — one method, one route

**Justification against Constraint 3.** The KPI *definitions* already exist and are not touched:
`compute_kpis` is imported and called unmodified. The *data* already exists: `CallSession.created_at`
is a persisted column. What is missing is purely the ability to ask the existing question over a date
range. That is access, not a new feature — the same reasoning that authorised Cookbook 4's
`session_list`. I am not inventing a metric; I am removing a hardcoded `WHERE`-less scan.

**File:** `apps/business-api/src/business_api/repositories.py`
**Placement:** immediately after `telemetry_timeline()`, at the end of `SupervisionRepository`.
**Existing code modified: none.**

```python
    def analytics_trend(self, days: int = 7) -> dict:
        """Windowed KPI bundle (current vs previous equal window) + daily volume buckets.

        Reuses compute_kpis unchanged; only the time filter is new. Buckets are cut in the
        business timezone so a "day" on the chart matches a day on the floor.
        """
        from datetime import datetime, timedelta, timezone

        tz_name = os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis")
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)

        def _bundle(start: datetime, end: datetime) -> Kpis:
            window = (CallSession.created_at >= start, CallSession.created_at < end)
            total = self._s.scalar(
                select(func.count()).select_from(CallSession).where(*window)) or 0
            resolved = self._s.scalar(
                select(func.count()).select_from(CallSession).where(
                    *window, CallSession.final_disposition == "resolved")) or 0
            escalated = self._s.scalar(
                select(func.count()).select_from(CallSession).where(
                    *window, CallSession.final_disposition == "escalated")) or 0
            avg = self._s.scalar(
                select(func.coalesce(func.avg(CallSession.max_frustration_score), 0)).where(*window))
            return compute_kpis(total, resolved, escalated, avg)

        local_day = func.date(func.timezone(tz_name, CallSession.created_at))
        rows = self._s.execute(
            select(local_day.label("day"), func.count().label("n"))
            .where(CallSession.created_at >= previous_start)
            .group_by(local_day)
        ).all()
        buckets = {str(r.day): int(r.n) for r in rows}

        daily = []
        for offset in range(days):
            cur = (current_start + timedelta(days=offset)).date().isoformat()
            prev = (previous_start + timedelta(days=offset)).date().isoformat()
            daily.append({
                "day": cur,
                "current": buckets.get(cur, 0),
                "previous": buckets.get(prev, 0),
            })

        return {
            "days": days,
            "timezone": tz_name,
            "current": _bundle(current_start, now).__dict__,
            "previous": _bundle(previous_start, current_start).__dict__,
            "daily": daily,
        }
```

`os` is **already imported** at the top of `main.py` but **not** in `repositories.py` — add
`import os` to the existing `from __future__` block region of `repositories.py`. This is the only
import addition. `Kpis` and `compute_kpis` are already imported there
(`from business_api.kpis import Kpis, compute_kpis`).

`func.timezone(tz_name, ts)` is the Postgres `timezone(text, timestamptz)` function. `repositories.py`
is already Postgres-bound (JSONB models, advisory locks), so this introduces no new portability
constraint. It matters: without it, `func.date()` cuts days in the **database session timezone**,
which for a UTC container silently shifts every Tunisian day boundary by one hour and misfiles the
23:00–00:00 sessions (G9).

**File:** `apps/business-api/src/business_api/main.py`
**Placement:** immediately after the `telemetry_timeline` route, before `audit_verify`.
**Existing code modified: none.**

```python
@app.get("/api/v1/analytics/trend")
def analytics_trend(session: DbSession, role: SuperviseurRole, days: int = 7) -> dict:
    """Windowed KPIs versus the preceding equal window, plus daily volume buckets."""
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return SupervisionRepository(session).analytics_trend(days)
```

`SuperviseurRole`, matching every sibling analytics route. The `1…90` clamp is not decoration: `days`
reaches a `timedelta` and drives a Python loop, so an unbounded value is a trivially reachable
resource sink from an authenticated seat.

### 3.3 CORS / middleware

**No change.** Per the Feature 0 decision, the admin dashboard reaches the backend through the
TanStack server proxy; the browser never contacts `:8108`. `CORS_ORIGINS` stays as-is.

---

## §4 — Frontend implementation plan

### 4.0 File manifest

| Action | Path |
|---|---|
| NEW | `src/lib/api/analytics.server.ts` |
| NEW | `src/lib/nexus/analytics-view.ts` |
| MOD | `src/lib/nexus/query-keys.ts` (+`analyticsKeys`) |
| MOD | `src/components/nexus/blocks.tsx` (`delta` → optional, 2 components) |
| MOD | `src/lib/nexus/data.ts` (remove 6 exports — **grep first**, see G8) |
| REWRITE | `src/routes/overview.tsx` |
| REWRITE | `src/routes/analytics.tsx` |

No new npm dependencies. No new design tokens. No `status.ts` change. No `nav.ts` change — both routes
already exist in the `INSIGHTS` section with their shortcuts, so unlike Cookbook 8 there is nothing to
register and `routeTree.gen.ts` is untouched.

### 4.1 Why the two pages diverge

Stated plainly because it is a visible product decision, not a technical one: today `/analytics`
renders a strict subset of `/overview`. Wiring both to the same four endpoints would produce two live
pages showing the same numbers, and the sidebar would offer the user a choice with no consequence.
The backend splits cleanly along an existing seam — `kpis()` / `system_overview()` are **cumulative,
all-time, no time filter**, while the new trend endpoint is **windowed and comparative**. I let that
seam decide: current state on `/overview`, movement on `/analytics`. Every heading on each page is
backed by a different query.

### 4.2 `src/lib/api/analytics.server.ts` (new)

```ts
import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware } from "@/lib/api/middleware";
import { inputValidator } from "@/lib/api/validation";

export type KpiBundle = {
  total_sessions: number;
  resolved: number;
  escalated: number;
  containment_rate: number;   // 0..1, NOT a percentage
  escalation_rate: number;    // 0..1
  avg_frustration: number;
};

export type PlatformMetrics = {
  total_calls: number;
  total_turns: number;
  total_verdicts: number;
  total_actions: number;
  total_audit_entries: number;
  total_customers: number;
  total_escalations: number;
};

/** `status` is deliberately absent from this type: the backend hardcodes it. See Cookbook 9 §0. */
export type ServiceEntry = { name: string; port: number; domain: string };

export type SystemOverview = { metrics: PlatformMetrics; services: ServiceEntry[] };

export type VerdictDistribution = { authorized: number; refused: number; escalated: number };

export type TrendPoint = { day: string; current: number; previous: number };

export type AnalyticsTrend = {
  days: number;
  timezone: string;
  current: KpiBundle;
  previous: KpiBundle;
  daily: TrendPoint[];
};

export const getKpis = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async ({ context }) =>
    businessApi<KpiBundle>("/api/v1/kpis", { role: context.session.role }),
  );

export const getSystemOverview = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async ({ context }) => {
    const raw = await businessApi<{
      metrics: PlatformMetrics;
      services: Array<ServiceEntry & { status?: string }>;
    }>("/api/v1/system/overview", { role: context.session.role });

    // Strip `status` at the boundary so no component can render it by accident.
    return {
      metrics: raw.metrics,
      services: raw.services.map(({ name, port, domain }) => ({ name, port, domain })),
    } satisfies SystemOverview;
  });

export const getVerdictDistribution = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async ({ context }) => {
    const raw = await businessApi<{ verdict_distribution: VerdictDistribution }>(
      "/api/v1/telemetry/timeline",
      { role: context.session.role },
    );
    return raw.verdict_distribution;
  });

export const getAnalyticsTrend = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .inputValidator((raw: unknown) => {
    const days = Number((raw as { days?: unknown })?.days ?? 7);
    return { days: [7, 14, 30].includes(days) ? days : 7 };
  })
  .handler(async ({ data, context }) =>
    businessApi<AnalyticsTrend>("/api/v1/analytics/trend", {
      query: { days: data.days },
      role: context.session.role,
    }),
  );
```

Three deliberate choices:

- **`getSystemOverview` discards `status` server-side, not in the component.** A component-level
  omission is one careless `{...service}` spread away from leaking. Dropping it at the boundary means
  the falsehood never enters the client bundle, and `ServiceEntry` has no field to render.
- **`getVerdictDistribution` discards `timeline`.** The 50 timeline points are unusable (G4) and
  shipping them would inflate every payload for nothing.
- **`days` is whitelisted to `[7, 14, 30]`**, matching the segmented control exactly. Anything else
  falls back to 7 rather than erroring — a bad query string should not blank the page.

### 4.3 `src/components/nexus/blocks.tsx` — the only design-system change

```diff
 export function HeroStat({
   label, value, delta, context, series,
 }: {
   label: string;
   value: string;
-  delta: number;
+  delta?: number;
   context: string;
   series?: number[];
 }) {
   return (
     <Card className="flex flex-col justify-between">
       <div className="flex items-start justify-between gap-sp-5">
         <p className="t-micro text-ink-5">{label}</p>
-        <Delta value={delta} />
+        {delta === undefined ? null : <Delta value={delta} />}
       </div>
```

```diff
 export function StatCard({
   label, value, delta, good, context, meta,
 }: {
   label: string;
   value: string;
-  delta: number;
+  delta?: number;
   good?: boolean | null;
   context: string;
   meta?: string;
 }) {
   return (
     <Card>
       <div className="flex items-start justify-between gap-sp-5">
         <p className="t-micro text-ink-5">{label}</p>
-        <Delta value={delta} good={good ?? null} />
+        {delta === undefined ? null : <Delta value={delta} good={good ?? null} />}
       </div>
```

That is the entire diff. **No token, colour, spacing, radius or typography change; no markup change
when `delta` is supplied.** Existing call sites pass a number and render pixel-identically — the
flex row keeps `justify-between`, so with the delta omitted the label sits left exactly as it does
today, matching the `meta`/`series` optional-slot pattern the file already uses twice.

The alternative was to keep `delta` required and feed it a computed number everywhere. On `/overview`
that number would have to be invented: `total_turns` is a lifetime count with nothing to compare
against. Constraint 4 forbids inventing backend behaviour to make the UI easier, and a fabricated
`+12.4 %` on an audit console is exactly the failure mode §0 is about. Precedent: Feature 1 already
modified `primitives.tsx` (`Segmented` → `type="button"`) when a shared primitive's contract was
wrong for real data.

### 4.4 `src/lib/nexus/analytics-view.ts` (new — pure, unit-testable)

```ts
import type { KpiBundle, TrendPoint, VerdictDistribution } from "@/lib/api/analytics.server";

/** Ratios arrive as 0..1 from `_ratio`. Render as a percentage with one decimal. */
export function formatRatio(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

/**
 * Percentage change between two periods.
 * Returns undefined when the previous period has no data — a jump from 0 has no
 * meaningful percentage, and "+100%" would be a fabrication.
 */
export function deltaPct(current: number, previous: number): number | undefined {
  if (!previous) return undefined;
  return Number((((current - previous) / previous) * 100).toFixed(1));
}

/** Absolute-point difference for values that are already rates. */
export function deltaPoints(current: number, previous: number, previousTotal: number): number | undefined {
  if (!previousTotal) return undefined;
  return Number(((current - previous) * 100).toFixed(1));
}

/** "2026-08-03" -> "Aug 3". Date-only string, parsed as UTC-safe parts, never `new Date(s)`. */
export function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${MONTHS[(month ?? 1) - 1]} ${day ?? ""}`.trim();
}

/** LineChart divides by `data.length - 1` and spreads into Math.max. Both break under 2 points. */
export function isChartable(daily: TrendPoint[]): boolean {
  return daily.length >= 2 && daily.some((d) => d.current > 0 || d.previous > 0);
}

export function verdictTotal(v: VerdictDistribution): number {
  return v.authorized + v.refused + v.escalated;
}

export function verdictShare(count: number, total: number): string {
  return total ? `${((count / total) * 100).toFixed(0)}% of the last ${total}` : "No verdicts yet";
}

/** An empty estate and a 0%-containment estate both report 0.0. Say which one it is. */
export function rateContext(bundle: KpiBundle, label: string): string {
  return bundle.total_sessions === 0
    ? "No sessions recorded yet"
    : `${label} across ${bundle.total_sessions} sessions`;
}
```

`dayLabel` deliberately avoids `new Date("2026-08-03")`, which JavaScript parses as **UTC midnight**
and then renders in local time — west of Greenwich that prints the previous day. Africa/Tunis is
UTC+1 so it happens to be safe today, but the bug is silent, environment-dependent, and this codebase
has already been bitten by date handling twice (Cookbook 2's `getDay(` ban, Cookbook 3's inverted
timezone rule). String-splitting cannot drift.

### 4.5 `src/lib/nexus/query-keys.ts` (modified)

```ts
export const analyticsKeys = {
  all: ["analytics"] as const,
  kpis: () => [...analyticsKeys.all, "kpis"] as const,
  system: () => [...analyticsKeys.all, "system"] as const,
  verdicts: () => [...analyticsKeys.all, "verdicts"] as const,
  trend: (days: number) => [...analyticsKeys.all, "trend", days] as const,
};
```

`trend` is keyed on `days` so switching the window is a cache hit on return, consistent with
`availabilityKeys` from Feature 2.

### 4.6 `src/routes/overview.tsx` (rewritten)

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, Avatar, PresenceDot, Token, EmptyState } from "@/components/nexus/primitives";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getKpis, getSystemOverview, getVerdictDistribution } from "@/lib/api/analytics.server";
import { listAdvisors } from "@/lib/api/advisors.server";
import { analyticsKeys, queryKeys } from "@/lib/nexus/query-keys";
import { formatRatio, rateContext, verdictShare, verdictTotal } from "@/lib/nexus/analytics-view";
import { advisorStatusKey, advisorPresenceLabel } from "@/lib/nexus/advisor-view";
import { formatInteger, formatCompact, initials } from "@/lib/nexus/format";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/overview")({
  head: () => ({
    meta: [
      { title: "Overview — Nexus" },
      { name: "description", content: "Platform totals, containment KPIs and who is on the floor." },
      { property: "og:title", content: "Overview — Nexus" },
      { property: "og:description", content: "Current state of the support platform." },
    ],
  }),
  component: OverviewPage,
});

function OverviewPage() {
  const kpis = useQuery({ queryKey: analyticsKeys.kpis(), queryFn: () => getKpis() });
  const system = useQuery({ queryKey: analyticsKeys.system(), queryFn: () => getSystemOverview() });
  const verdicts = useQuery({ queryKey: analyticsKeys.verdicts(), queryFn: () => getVerdictDistribution() });
  const advisors = useQuery({
    queryKey: queryKeys.advisors({ includeInactive: false }),
    queryFn: () => listAdvisors({ data: { includeInactive: false } }),
  });

  return (
    <>
      {/* ---- Containment KPIs (all-time; no comparison exists, so no deltas) ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        {kpis.isPending ? (
          <>
            <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
          </>
        ) : kpis.isError ? (
          <div className="xl:col-span-4">
            <ErrorState message={errorMessage(kpis.error)} onRetry={() => kpis.refetch()} />
          </div>
        ) : (
          <>
            <HeroStat
              label="Total sessions"
              value={formatCompact(kpis.data.total_sessions)}
              context="All sessions ever recorded"
            />
            <StatCard
              label="Containment rate"
              value={formatRatio(kpis.data.containment_rate)}
              context={rateContext(kpis.data, "Resolved without escalation")}
              meta={`${formatInteger(kpis.data.resolved)} resolved`}
            />
            <StatCard
              label="Escalation rate"
              value={formatRatio(kpis.data.escalation_rate)}
              context={rateContext(kpis.data, "Handed to an advisor")}
              meta={`${formatInteger(kpis.data.escalated)} escalated`}
            />
            <StatCard
              label="Avg. frustration"
              value={kpis.data.avg_frustration.toFixed(2)}
              context="Mean peak frustration per session"
            />
          </>
        )}
      </PageSection>

      {/* ---- Policy verdict mix (last 100 verdicts) ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-3">
        {verdicts.isPending ? (
          <><CardSkeleton /><CardSkeleton /><CardSkeleton /></>
        ) : verdicts.isError ? (
          <div className="xl:col-span-3">
            <ErrorState message={errorMessage(verdicts.error)} onRetry={() => verdicts.refetch()} />
          </div>
        ) : (
          (() => {
            const total = verdictTotal(verdicts.data);
            return (
              <>
                <StatCard label="Authorized" value={formatInteger(verdicts.data.authorized)}
                  context={verdictShare(verdicts.data.authorized, total)} />
                <StatCard label="Refused" value={formatInteger(verdicts.data.refused)}
                  context={verdictShare(verdicts.data.refused, total)} />
                <StatCard label="Escalated" value={formatInteger(verdicts.data.escalated)}
                  context={verdictShare(verdicts.data.escalated, total)} />
              </>
            );
          })()
        )}
      </PageSection>

      <PageSection className="grid gap-sp-6 xl:grid-cols-2">
        {/* ---- Team availability (real: advisor registry) ---- */}
        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader title="Team Availability" subtitle="Advisors currently on the floor." />
          </div>
          {advisors.isPending ? (
            <div className="px-sp-7 pb-sp-7"><CardSkeleton /></div>
          ) : advisors.isError ? (
            <div className="px-sp-7 pb-sp-7">
              <ErrorState message={errorMessage(advisors.error)} onRetry={() => advisors.refetch()} />
            </div>
          ) : advisors.data.length === 0 ? (
            <div className="px-sp-7 pb-sp-7">
              <EmptyState title="No advisors" description="Register an advisor to see availability here." />
            </div>
          ) : (
            <ul>
              {advisors.data.map((a) => (
                <li key={a.id}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
                  <Avatar initials={initials(a.full_name)} name={a.full_name} />
                  <div className="min-w-0">
                    <p className="t-ui truncate text-ink-1">{a.full_name}</p>
                    <p className="t-caption inline-flex items-center gap-sp-3 text-ink-4">
                      <PresenceDot live={advisorStatusKey(a.status) === "online"} />
                      {advisorPresenceLabel(a.status)}
                    </p>
                  </div>
                  <span className="t-label ml-auto text-ink-3">{a.language ?? "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ---- Service inventory. NO status: see Cookbook 9 §0. ---- */}
        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader
              title="Service Inventory"
              subtitle="Deployed services and the domain each owns. Health is not monitored."
            />
          </div>
          {system.isPending ? (
            <div className="px-sp-7 pb-sp-7"><CardSkeleton /></div>
          ) : system.isError ? (
            <div className="px-sp-7 pb-sp-7">
              <ErrorState message={errorMessage(system.error)} onRetry={() => system.refetch()} />
            </div>
          ) : (
            <ul>
              {system.data.services.map((s) => (
                <li key={`${s.name}-${s.port}`}
                    className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
                  <div className="min-w-0">
                    <p className="t-ui truncate text-ink-1">{s.name}</p>
                    <p className="t-caption truncate text-ink-4">{s.domain}</p>
                  </div>
                  <Token className="ml-auto">{s.port}</Token>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </PageSection>

      {/* ---- Platform totals ---- */}
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        {system.isPending || system.isError ? null : (
          <>
            <StatCard label="Customers" value={formatInteger(system.data.metrics.total_customers)}
              context="Records in the CRM" />
            <StatCard label="Turns" value={formatCompact(system.data.metrics.total_turns)}
              context="Transcript turns persisted" />
            <StatCard label="Actions" value={formatInteger(system.data.metrics.total_actions)}
              context="Entries in the action ledger" />
            <StatCard label="Audit entries" value={formatCompact(system.data.metrics.total_audit_entries)}
              context="Hash-chained audit records" />
          </>
        )}
      </PageSection>
    </>
  );
}
```

Note `key={`${s.name}-${s.port}`}` rather than `key={s.name}`: the mock keyed on `b.email` / `a.name`,
but two of the eleven services (`ocs-billing-sim` and `nms-sim`, per the Phase 1 port audit) collide
on port 8107/8108 elsewhere in the compose file, and name-only keys are fragile if the list ever
gains a duplicate. Composite key, zero cost.

### 4.7 `src/routes/analytics.tsx` (rewritten)

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Card, CardHeader, Segmented, EmptyState } from "@/components/nexus/primitives";
import { HeroStat, StatCard, LineChart, Legend } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getAnalyticsTrend } from "@/lib/api/analytics.server";
import { analyticsKeys } from "@/lib/nexus/query-keys";
import {
  dayLabel, deltaPct, deltaPoints, formatRatio, isChartable,
} from "@/lib/nexus/analytics-view";
import { formatCompact } from "@/lib/nexus/format";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/analytics")({
  head: () => ({
    meta: [
      { title: "Analytics — Nexus" },
      { name: "description", content: "Windowed volume and containment trends against the previous period." },
      { property: "og:title", content: "Analytics — Nexus" },
      { property: "og:description", content: "Trend analysis across the support platform." },
    ],
  }),
  component: AnalyticsPage,
});

const RANGES = [7, 14, 30] as const;

function AnalyticsPage() {
  const [days, setDays] = useState<number>(7);

  const trend = useQuery({
    queryKey: analyticsKeys.trend(days),
    queryFn: () => getAnalyticsTrend({ data: { days } }),
    placeholderData: keepPreviousData,
  });

  const rangeControl = (
    <Segmented
      items={RANGES.map((d) => ({ label: `${d}d`, value: String(d) }))}
      active={String(days)}
      onSelect={(value: string) => setDays(Number(value))}
    />
  );

  if (trend.isPending) {
    return (
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
      </PageSection>
    );
  }

  if (trend.isError) {
    return (
      <PageSection>
        <ErrorState message={errorMessage(trend.error)} onRetry={() => trend.refetch()} />
      </PageSection>
    );
  }

  const { current, previous, daily } = trend.data;

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <HeroStat
          label={`Sessions (${days}d)`}
          value={formatCompact(current.total_sessions)}
          delta={deltaPct(current.total_sessions, previous.total_sessions)}
          context={`Compared with the previous ${days} days`}
          series={daily.map((d) => d.current)}
        />
        <StatCard
          label="Containment rate"
          value={formatRatio(current.containment_rate)}
          delta={deltaPoints(current.containment_rate, previous.containment_rate, previous.total_sessions)}
          good
          context="Resolved without escalation"
          meta={`Previous: ${formatRatio(previous.containment_rate)}`}
        />
        <StatCard
          label="Escalation rate"
          value={formatRatio(current.escalation_rate)}
          delta={deltaPoints(current.escalation_rate, previous.escalation_rate, previous.total_sessions)}
          good={false}
          context="Handed to an advisor"
          meta={`Previous: ${formatRatio(previous.escalation_rate)}`}
        />
        <StatCard
          label="Avg. frustration"
          value={current.avg_frustration.toFixed(2)}
          delta={deltaPct(current.avg_frustration, previous.avg_frustration)}
          good={false}
          context="Mean peak frustration per session"
          meta={`Previous: ${previous.avg_frustration.toFixed(2)}`}
        />
      </PageSection>

      <PageSection>
        <Card>
          <CardHeader
            title="Volume Trend"
            subtitle={`Daily sessions, ${trend.data.timezone}.`}
            action={
              <div className="flex items-center gap-sp-6">
                <Legend items={[{ label: "This period", strong: true }, { label: "Previous" }]} />
                {rangeControl}
              </div>
            }
          />
          <div className="mt-sp-7">
            {isChartable(daily) ? (
              <LineChart data={daily.map((d) => ({
                day: dayLabel(d.day), current: d.current, previous: d.previous,
              }))} />
            ) : (
              <EmptyState
                title="Not enough data"
                description={`No sessions were recorded in the last ${days} days.`}
              />
            )}
          </div>
        </Card>
      </PageSection>
    </>
  );
}
```

**`isChartable` is not defensive padding — it prevents a hard crash.** `LineChart` computes
`Math.max(...values) * 1.08` and `100 / (data.length - 1)`. With zero points `Math.max()` of an empty
spread is `-Infinity`; with one point the step is `100 / 0 = Infinity`. Either produces `NaN` in every
`points` coordinate and React renders a broken `<polyline>`. An estate with a quiet week is not an
edge case, it is Tuesday.

`keepPreviousData` keeps the previous window's chart on screen while the new one loads, so switching
7 → 30 does not flash a skeleton over the whole page.

**Verify the `Segmented` `items` shape before wiring.** Feature 2 already ships a live range selector
on `/availability` (7/14/30) — copy that call site verbatim rather than trusting the shape written
above. It is the closest existing equivalent and Constraint 1 requires reusing it.

### 4.8 `src/lib/nexus/data.ts` (modified)

Remove `OVERVIEW_STATS`, `CALL_VOLUME_SERIES`, `RESOLUTION_SERIES`, `HERO_SPARKLINE`,
`BILLING_ACTIVITY`, `ADVISOR_TEAM`.

**Run this first (G8):**

```bash
grep -rn "OVERVIEW_STATS\|CALL_VOLUME_SERIES\|RESOLUTION_SERIES\|HERO_SPARKLINE\|BILLING_ACTIVITY\|ADVISOR_TEAM" Frontend/admin_dashboard/src
```

Expect hits only in `overview.tsx` and `analytics.tsx`. **`src/routes/index.tsx` (`419e7d34`) is
unread** and is the most likely third consumer — if it appears, keep the exports it needs and remove
only the rest. Deleting an export that `index.tsx` imports breaks the landing route, and the type
error would only surface at build time.

---

## §5 — Findings

**G1 — The service health matrix is fabricated.** Eleven hardcoded `"online"` literals, no probe.
Would report a fully healthy platform during a total outage. §0. **Most dangerous finding in the
series** — every prior finding produced a wrong or blank value; this one produces false assurance in
exactly the situation where an operator most needs the truth. Never rendered; stripped server-side.

**G2 — `/api/v1/kpis` breaks the envelope convention.** Every other collection route wraps its payload
(`{"advisors": …}`, `{"verdicts": …}`, `{"rules": …}`, `{"actions": …}`). This one returns
`.__dict__` **flat**. Verified in `main.py`, not assumed. `data.kpis` would be `undefined` and every
card would render `NaN`.

**G3 — `_ratio` conflates "no data" with "zero performance."** `return round(...) if denominator else
0.0`. A brand-new estate reports 0.0 % containment, identical to a catastrophically failing one.
Mitigated in `rateContext()` by branching on `total_sessions`. Not a backend fix — changing the return
to `None` would alter an existing contract that `tests` and the agent may depend on.

**G4 — `telemetry_timeline` timestamps are undated and untimezoned.** `strftime("%H:%M:%S")` yields
`"14:32:07"` — no date, no offset. Fifty points spanning several days all collapse onto a 24-hour
clock and silently wrap at midnight, so the series is non-monotonic and unplottable. The `timeline`
array is therefore **discarded at the server boundary**; only `verdict_distribution` is used. This is
why the new endpoint exists rather than reusing this one.

**G5 — `LineChart` has no empty guard.** `Math.max(...[])` → `-Infinity`; `100 / (1 - 1)` → `Infinity`.
Crashes on 0 or 1 points. Guarded call-side by `isChartable` rather than patched, keeping the
design-system diff to the two `delta` props.

**G6 — Chip trap, seventh recurrence.** `Advisor.status IN ('available','busy','offline')`. `status.ts`
contains `offline` but **not `available` and not `busy`** — `StatusChip` returns `null` for both, so
two of three advisor states would render blank, including the one that matters most on a
"who is on the floor" panel. **Resolved by reuse, not re-derivation:** Feature 1 is applied and already
ships `src/lib/nexus/advisor-view.ts` with this mapping settled. Import `advisorStatusKey` /
`advisorPresenceLabel` from it. Re-deciding here would risk `/overview` and `/advisors` disagreeing
about the same advisor. **Ninth consecutive cookbook with zero `status.ts` changes.**

**G7 — `StatCard.delta` / `HeroStat.delta` are required, but no endpoint returns a comparison.** The
single reason a design-system file is touched. §4.3.

**G8 — `data.ts` export removal is not obviously safe.** `src/routes/index.tsx` is unread and may
import the overview mocks. Grep before deleting.

**G9 — Day bucketing in the wrong timezone is silent.** A bare `func.date(created_at)` cuts days in
the DB session timezone. On a UTC container every Africa/Tunis day boundary shifts by an hour and
23:00–00:00 local sessions are filed to the wrong bar. Fixed by `func.timezone(tz_name, …)` using the
same `CALLBACK_TIMEZONE` env `availability.py` already reads — one business timezone, one source.

**G10 — `/analytics` and `/overview` are currently the same page.** Resolved by splitting along the
cumulative/windowed seam the backend already has (§4.1).

**G11 — `BarChart` becomes unused.** Its contract is `{week, ai, advisor}[]` — an AI-versus-advisor
resolution split. **The backend has no advisor-resolution attribution at all:** `final_disposition` is
`resolved | escalated | dropped | abandoned`, which records *whether* a session escalated, never *who*
closed it. Building that attribution is new business logic → **flagged, not built** (§8.2). Following
the Feature 5 precedent ("New ticket" removed, not disabled), the Resolution Mix card is **removed**
rather than shown empty. `BarChart` stays exported and unreferenced; it is not dead code to delete,
because §8.2 may bring it straight back.

**G12 — Billing Activity has no estate-wide source.** The `Invoice` model exists, but the only route
that surfaces invoices is `customer_360`, which is per-customer and returns just unpaid ones
(`if i.status != "paid"`). A "latest invoice movements" feed across all customers has no endpoint and
no repository method. Panel **removed**; flagged in §8.3. Note the mock's `StatusChip status={b.status}`
would also have hit the chip trap — `paid`/`overdue`/`refunded` are in `status.ts`, but `Invoice.status`
is not constrained to those three anywhere I have read.

**G13 — `avg_frustration` percentage deltas are shaky.** It is a bounded score, not a count, so a
percentage change between `1.20` and `1.44` reads as "+20 %" and overstates a small absolute move.
Kept as a percentage for consistency with the other cards, `good={false}`. §8.4 offers absolute-points
instead.

**G14 — `verdict_distribution` is a rolling 100, not a period.** It ignores the `/analytics` window
entirely, which is why it lives on `/overview` (current state) and is labelled *"of the last N"* via
`verdictShare`, never as a rate.

**G15 — `formatPercent` was not reused.** `format.ts` exports it, but whether it expects `0..1` or
`0..100` is unverified, and feeding it the wrong scale yields a plausible-looking wrong number.
`formatRatio` is explicit about the `×100`. **Verify `formatPercent`'s contract at apply time and
collapse the two if they agree.**

---

## §6 — Validation checklist

**Backend**

- [ ] `import os` added to `repositories.py`; `Kpis` / `compute_kpis` imports unchanged.
- [ ] `kpis.py` **byte-identical** to `fb5afcd8` — `compute_kpis` reused, never edited.
- [ ] `kpis()`, `system_overview()`, `telemetry_timeline()`, and all 34 existing routes byte-identical.
- [ ] `GET /api/v1/analytics/trend` returns 200 for `days=7|14|30`, 400 for `days=0` and `days=91`.
- [ ] Route returns 403 for `X-Role: conseiller`, 200 for `superviseur` and `administrateur`.
- [ ] `current.total_sessions` equals a manual `COUNT(*)` over the same window.
- [ ] `daily` has exactly `days` entries, ascending, no gaps — including days with zero sessions.
- [ ] A session written at 23:30 Africa/Tunis lands on that local day, not the next.
- [ ] Empty database → 200 with all zeros, no exception, no division by zero.

**Frontend**

- [ ] `tsc --noEmit` clean.
- [ ] `lint` returns exactly the **36-problem baseline** (28 prettier errors + 8 warnings).
- [ ] `build` exits 0.
- [ ] Grep for the six removed `data.ts` exports returns **zero** hits after the rewrite.
- [ ] **Zero** direct browser requests to `:8108` (DevTools Network, both routes).
- [ ] No new npm dependency; `package.json` untouched.
- [ ] `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/overview.tsx src/routes/analytics.tsx src/lib/nexus/analytics-view.ts` → no hits.
- [ ] `grep -rn 'getDay(\|getHours(\|toLocaleString(\|new Date(' src/lib/nexus/analytics-view.ts` → no hits.
- [ ] `blocks.tsx` diff is **exactly** two prop signatures and two conditional renders.
- [ ] `/customers`, `/tickets`, `/calls` and every other `StatCard` consumer render pixel-identically.
- [ ] `status.ts` untouched; `routeTree.gen.ts` untouched; `nav.ts` untouched.
- [ ] The string `"online"` does not appear in the client bundle from this feature.
- [ ] Service inventory shows name, domain and port — and **no** status indicator of any kind.
- [ ] Advisor presence uses Feature 1's `advisor-view.ts`; `available` and `busy` both render.
- [ ] Backend stopped → both routes show `ErrorState` with a retry, no white screen.
- [ ] Empty database → `/analytics` shows "Not enough data", not a broken chart.
- [ ] Exactly one session in the window → still "Not enough data", no `Infinity` in the DOM.
- [ ] `previous.total_sessions === 0` → deltas are **absent**, not `+100%`.
- [ ] Switching 7 → 14 → 30 keeps the old chart visible, refetches, and caches on return.

---

## §7 — Dependencies and ordering

Feature 9 depends on **Feature 0** (applied) and **Feature 1** (applied) only — `businessApi`,
`authedMiddleware`, `inputValidator`, `CardSkeleton`, `ErrorState`, `errorMessage`, `listAdvisors`,
`advisor-view.ts`.

It deliberately does **not** depend on Cookbook 4's `GET /api/v1/sessions`, even though bucketing that
list client-side would have avoided a backend change. Cookbooks 3–8 are written but unapplied, and a
cross-cookbook dependency would mean `/analytics` silently breaks if you apply them out of order. One
self-contained endpoint keeps Feature 9 applicable **today**, in isolation.

---

## §8 — Open questions

**§8.1 — Should service health become real?** This is the biggest open item in the series. Every
service already exposes `/health` (`service-auth` even defines `_HEALTH_PATHS`, and business-api's own
`/health` returns `{"status": "ok"}`). A real matrix means a fan-out of eleven short-timeout `httpx`
calls behind a small cache. That is new business logic, so Constraint 3 says I flag it.
**My recommendation: build it, as its own scoped feature.** Until then the console cannot answer
"is anything down?", and the current answer is worse than none. Confirm and I will write it as
Cookbook 10.

**§8.2 — Is AI-versus-advisor resolution a metric you want?** It is the one mock chart with no backend
analogue. It needs a new attribution concept — `final_disposition` records escalation, not authorship.
Minimal honest version: treat `resolved` as AI-contained and `escalated` as advisor-handled, which is
already exactly `containment_rate` and needs no new column. Say the word and Resolution Mix returns as
a containment-mix bar, reusing `BarChart` unmodified.

**§8.3 — Do you want a billing activity feed?** Needs a new repository method over `Invoice` ordered by
recency across all customers. Straightforward, but it is a new read surface for a domain no admin
cookbook has touched, so I did not assume it. Also confirm the allowed values of `Invoice.status` —
I have not read `billing.py` and cannot promise they all exist in `status.ts`.

**§8.4 — Frustration delta: percentage or absolute points?** Currently percentage (G13). Absolute
(`+0.24`) is arguably more honest for a bounded score. Your call; one-line change.

**§8.5 — Should the window selector persist in the URL?** Currently `useState`, so a reload returns to
7 days and a window cannot be shared in a link. TanStack Router `search` params would fix both. Not
done because no other page in the applied set does it, and I would rather not set a precedent
unilaterally.

**§8.6 — Is `/overview` or `/analytics` the intended landing page?** `src/routes/index.tsx` is unread.
If it redirects to `/overview`, the split in §4.1 is right as built. If it renders its own copy of the
overview mocks, it needs the same treatment and G8 becomes a blocker rather than a check.

**§8.7 — Rolling-100 verdict window.** `telemetry_timeline` hardcodes `.limit(100)`. On a busy estate
that may be under an hour of traffic while the card sits next to all-time KPIs. Should the verdict mix
be windowed to match `/analytics`? That would mean extending the new endpoint rather than reusing
telemetry.

**§8.8 — `avg_frustration` across all time is barely actionable.** It flattens every improvement into a
lifetime mean. It stays on `/overview` for completeness, but the windowed version on `/analytics` is
the one to watch. Consider dropping the all-time card.

---

## §9 — Flags raised outside this feature's scope

**§9.1 — `session_detail`'s unguarded `float(call.max_frustration_score)` is now three-way reachable.**
Cookbook 4 (`/calls`), Cookbook 8 (`/decisions`), and any drill-through added later. `kpis()` proves
the fix is already known in the same file — `func.coalesce(..., 0)`. One `or 0` closes it. Still unfixed.

**§9.2 — Port collision, unresolved since Phase 1.** `ocs-billing-sim` and `nms-sim` are both
documented on 8107/8108, colliding with `token-service` and `business-api`. The service inventory
panel will now display this to an operator, so it stops being a documentation wart and becomes a
visible inconsistency.

**§9.3 — `/overview` no longer justifies its "Overview & Analytics" title.** Renamed to "Overview" in
the `head` block, since analytics now genuinely live on the other route. `nav.ts`'s `PAGE_META` may
carry its own label — check it matches, though no code change is required for the page to work.
