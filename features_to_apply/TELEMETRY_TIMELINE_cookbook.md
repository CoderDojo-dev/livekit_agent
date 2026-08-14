# Cookbook — Telemetry Timeline Chart

**Branch:** `version_89` · **HEAD** `b5b0ac6018c26e4fd30fc64dba59ba1a9cc570f5`
**Scope:** `Frontend/admin_dashboard/src/**` only.
**Bundle:** 2 new files, 3 anchored edits. No new dependency, no new network request, no backend byte.

---

## §0 — Boundary declaration (read before anything else)

This bundle touches **five frontend files and nothing else**. It explicitly does **not**:

| Forbidden | Status in this bundle |
| --- | --- |
| Any `.py` file | ZERO touched |
| Backend logic / models / routing / behaviour | ZERO touched |
| `.github/workflows/**`, `Makefile`, `Dockerfile`, pipeline scripts | ZERO touched |
| Tests of any kind (unit, integration, QA scripts) | ZERO written |
| `pyproject.toml`, `package.json`, any library version | ZERO touched |
| `lib/nexus/status.ts` (the 27-key status truth table) | ZERO touched |
| New colours, hex, rgb, new theme tokens | ZERO introduced |

The backend contract is consumed **exactly as it already is**. The endpoint is not modified, not
extended, not re-shaped. We are only reading the half of the response that TypeScript was
throwing away.

---

## §1 — The gap, proven from source

### 1.1 The backend has always returned two halves

`packages/persistence/.../repositories.py` → `SupervisionRepository.telemetry_timeline()` (SHA `5247834e`):

```python
sessions = CallSession ORDER BY created_at DESC LIMIT 50
return {
    "timeline": [
        {
            "timestamp": created_at.strftime("%H:%M:%S") or "00:00:00",
            "duration": duration_seconds or 0,
            "frustration": float(max_frustration_score or 0.0),
            "disposition": final_disposition or "unknown",
        }
        for s in reversed(sessions)          # <-- reversed() => chronological ASC
    ],
    "verdict_distribution": {"authorized": ..., "refused": ..., "escalated": ...},
}
```

Three facts that drive every decision below:

1. `timeline` is **chronologically ascending** (`reversed()` of a `DESC LIMIT 50`). Left-to-right
   plotting is correct with no client-side sort.
2. `timestamp` is a **bare wall-clock `%H:%M:%S` string with no date component**. It cannot be
   passed to `new Date(...)`, cannot be compared, cannot be localised. It is echoed verbatim.
3. `duration` is **integer seconds**, `frustration` is a **float**. Both are already coalesced
   server-side, so neither is ever `null`.

### 1.2 The frontend typed only one half

`Frontend/admin_dashboard/src/lib/api/decisions.server.ts` (SHA `7408c43d`) — verbatim:

```ts
export const getVerdictDistribution = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) => {
    return businessApi<{
      verdict_distribution: VerdictDistribution;
    }>("/api/v1/telemetry/timeline", {
      method: "GET",
      role: context.session.role,
    });
  });
```

Types are erased at runtime. `businessApi` does `await response.json()`, so **all 50 points are
already decoded and sitting in memory** — TypeScript simply refused to admit they existed.

### 1.3 Neither consumer renders them — now verified by reading both routes

- **`routes/overview.tsx`** (SHA `8e31a6c1`) calls `getVerdictDistribution()` under
  `analyticsKeys.verdicts()` and reads exactly one field:
  `const mix = verdicts.data.verdict_distribution;` → three `StatCard`s. The `timeline` array is
  fetched over the wire on every Overview visit and dropped.
- **`routes/analytics.tsx`** (SHA `4d7ba82a`) does own a real `LineChart`, but it plots
  `getAnalyticsTrend` → `TrendPoint {day, current, previous}` from `/api/v1/analytics/trend`.
  That is **daily session counts**, a different dataset at a different granularity. It is not a
  duplicate of the timeline and it is not a substitute for it.

**Conclusion:** the gap is real, and it is a pure display gap. Zero backend work, zero new
requests. The data is already paid for.

---

## §2 — Architectural decisions and why

### D1 — Widen the wire type instead of adding a second server function

A new `getTelemetryTimeline()` server function would mean a **second HTTP round-trip to the exact
same URL** returning the exact same bytes. Instead the existing generic is widened to describe the
whole response. This is the truthful typing of what the endpoint already sends, it is
backwards-compatible (`overview.tsx`'s `.verdict_distribution` keeps working untouched), and it
costs nothing at runtime.

### D2 — Reuse the `analyticsKeys.verdicts()` cache key. Do not use `supervision.telemetryTimeline`

`query-keys.ts` does pre-declare `queryKeys.supervision.telemetryTimeline`. Using it here would
create a **second cache entry for an identical payload**, i.e. a second fetch. Mounting the chart
under `analyticsKeys.verdicts()` makes Overview and Analytics share one cache entry: whichever tab
is visited first pays for the request, the other is a cache hit. `supervision.telemetryTimeline`
therefore stays intentionally unused, and this cookbook is the record of that decision.

### D3 — Mount on Analytics, leave `overview.tsx` byte-identical

Overview is a density-first landing grid (`xl:grid-cols-3` / `xl:grid-cols-4` of stat cards). A
220px chart does not belong there, and re-flowing that grid risks a layout regression on a screen
that currently works. Analytics is the charts surface and already owns the `Card` + `CardHeader` +
`Segmented` + `Legend` idiom. **`overview.tsx` is not edited at all** — it keeps its verdict mix and
now simply shares the payload.

### D4 — One metric at a time, not two y-axes on one plot

`duration` (seconds, tens-to-hundreds) and `frustration` (a small float) have no common scale.
Drawing both against independent invisible axes is the classic dual-axis lie. Instead a `Segmented`
control switches the plotted series, and the **hover readout always shows both values for the
hovered session** — so no information is lost and nothing is misrepresented.

### D5 — Hover state lifted out of the chart; no tooltip, no circles

The house chart idiom is `viewBox="0 0 100 100"` + `preserveAspectRatio="none"`, which stretches
geometry horizontally. A `<circle>` marker would render as a flattened ellipse and a floating
tooltip would need positioning maths against a stretched coordinate space. So: markers are
**lines only** (unaffected by stretch, with `vectorEffect="non-scaling-stroke"`), and the numeric
readout lives in a **fixed row inside the card**, which cannot overflow, cannot clip, and reads
identically on every viewport. Hover state lives in the caller, which keeps `blocks.tsx` a pure
stateless module — it has no `useState` import today and still won't.

### D6 — 50 x-axis labels are unreadable, so the axis is thinned

`LineChart` renders one label per point, which is fine for 7–30 daily buckets and unusable for 50.
`axisTicks()` emits at most six evenly-spaced anchors.

### D7 — Divide-by-zero is handled, unlike the existing `LineChart`

`LineChart` computes `max = Math.max(...values) * 1.08`; an all-zero series yields `max = 0` and
every coordinate becomes `NaN`. `metricMax()` floors the scale at `1`, so a fresh database with 50
zero-duration sessions draws a flat baseline instead of an invisible broken chart. The existing
`LineChart` is **not modified** — that latent edge case is logged in the status report, not fixed
here, because it is out of this bundle's scope.

### D8 — Function name `getVerdictDistribution` is deliberately NOT renamed

It is now a slight misnomer. Renaming it would ripple into `overview.tsx` and the cache-key
vocabulary for zero functional gain, and this phase is about adding reach, not churn. A comment
records it.

---

## §3 — File manifest

| # | File | Action | Nature |
| --- | --- | --- | --- |
| 1 | `Frontend/admin_dashboard/src/lib/api/decisions.server.ts` | EDIT | type-only widening + 2 new exported types |
| 2 | `Frontend/admin_dashboard/src/lib/nexus/telemetry-view.ts` | **NEW** | pure helpers, zero JSX, zero I/O |
| 3 | `Frontend/admin_dashboard/src/components/nexus/blocks.tsx` | EDIT | additive: one new exported chart primitive |
| 4 | `Frontend/admin_dashboard/src/components/nexus/telemetry-timeline.tsx` | **NEW** | feature component (owns its query + local UI state) |
| 5 | `Frontend/admin_dashboard/src/routes/analytics.tsx` | EDIT | 1 import line + 3-line mount |

No existing export is renamed, re-signed or removed anywhere in this bundle.

---

## §4 — The patches

### PATCH 1 — `lib/api/decisions.server.ts`

**Find this exact block** (it is the last block in the file):

```ts
export const getVerdictDistribution = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) => {
    return businessApi<{
      verdict_distribution: VerdictDistribution;
    }>("/api/v1/telemetry/timeline", {
      method: "GET",
      role: context.session.role,
    });
  });
```

**Replace it with:**

```ts
/** One recorded call session, exactly as SupervisionRepository.telemetry_timeline() serialises it.
 *  `timestamp` is a bare wall-clock "%H:%M:%S" string (created_at.strftime) with NO date part:
 *  echo it verbatim, never parse it as a Date. `duration` is integer seconds, `frustration` a
 *  float, `disposition` falls back to the literal "unknown" — the backend coalesces all three,
 *  so none of them is ever null. The array arrives chronologically ASCENDING (the repository
 *  reverses a DESC LIMIT 50), so index order is already plot order. */
export type TelemetryPoint = {
  timestamp: string;
  duration: number;
  frustration: number;
  disposition: string;
};

/** The endpoint always returned both halves; only `verdict_distribution` was ever typed, so the
 *  50-point `timeline` was decoded at runtime and then discarded by TypeScript. Widening the
 *  generic is the truthful description of the existing response — it adds no request. */
export type TelemetrySnapshot = {
  timeline: TelemetryPoint[];
  verdict_distribution: VerdictDistribution;
};

/* Name kept for compatibility: overview.tsx and analyticsKeys.verdicts() already speak it.
 * It now returns the whole snapshot, of which the verdict mix is one field. */
export const getVerdictDistribution = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) => {
    return businessApi<TelemetrySnapshot>("/api/v1/telemetry/timeline", {
      method: "GET",
      role: context.session.role,
    });
  });
```

> `role: context.session.role` is preserved verbatim. `business-api.ts` no longer transmits it but
> every caller still passes it, and this bundle does not change that convention.

---

### PATCH 2 — NEW FILE `lib/nexus/telemetry-view.ts`

Create the file with exactly this content:

```ts
import { dispositionKey, dispositionLabel } from "@/lib/nexus/call-view";
import { formatDuration } from "@/lib/nexus/format";
import type { TelemetryPoint } from "@/lib/api/decisions.server";

/* Pure view helpers for /api/v1/telemetry/timeline. No JSX, no I/O, no Date parsing.
 * Chapter 9 rule: every value is formatted through format.ts, never inline. */

/** The two numeric series the endpoint carries. Label round-trip feeds <Segmented />. */
export const TELEMETRY_METRICS = [
  { id: "duration", label: "Duration" },
  { id: "frustration", label: "Frustration" },
] as const;

export type TelemetryMetric = (typeof TELEMETRY_METRICS)[number]["id"];

/** Mirrors isChartable(): one point cannot describe a trend, and the x-step divides by
 *  (length - 1), so two is the hard floor. Array.isArray also absorbs a malformed payload
 *  instead of letting a white screen through. */
export function isPlottable(points: TelemetryPoint[]): boolean {
  return Array.isArray(points) && points.length >= 2;
}

export function metricValues(points: TelemetryPoint[], metric: TelemetryMetric): number[] {
  return points.map((point) => (metric === "duration" ? point.duration : point.frustration));
}

/** 1.08 headroom matches LineChart. The floor of 1 is the difference from LineChart: an
 *  all-zero series there yields max = 0 and every coordinate becomes NaN. */
export function metricMax(values: number[]): number {
  const peak = Math.max(0, ...values);
  return peak > 0 ? peak * 1.08 : 1;
}

export function formatMetric(metric: TelemetryMetric, value: number): string {
  return metric === "duration" ? formatDuration(Math.round(value)) : value.toFixed(2);
}

export function metricUnit(metric: TelemetryMetric): string {
  return metric === "duration" ? "Call length (mm:ss)" : "Peak frustration score";
}

export function averageOf(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/** 50 crammed labels are unreadable, so only a handful of evenly spaced anchors are drawn.
 *  Labels are the raw "%H:%M:%S" strings — echoed, never parsed. */
export function axisTicks(
  points: TelemetryPoint[],
  maxTicks = 6,
): { index: number; label: string }[] {
  if (points.length === 0) return [];
  if (points.length <= maxTicks) {
    return points.map((point, index) => ({ index, label: point.timestamp }));
  }
  const stride = (points.length - 1) / (maxTicks - 1);
  const seen = new Set<number>();
  const ticks: { index: number; label: string }[] = [];
  for (let step = 0; step < maxTicks; step += 1) {
    const index = Math.round(step * stride);
    if (seen.has(index)) continue;
    seen.add(index);
    ticks.push({ index, label: points[index]!.timestamp });
  }
  return ticks;
}

/** "09:12:04 -> 17:44:31", built from the first and last stamps verbatim. */
export function timelineSpan(points: TelemetryPoint[]): string {
  if (points.length === 0) return "\u2014";
  const first = points[0]!.timestamp;
  const last = points[points.length - 1]!.timestamp;
  return first === last ? first : `${first} \u2192 ${last}`;
}

/** Same achromatic token vocabulary as sentimentTone() in call-view.ts. No new colours:
 *  every class below already ships in the product. dispositionKey() is total, so the
 *  default arm only catches in-progress / "unknown". */
export function dispositionTone(disposition: string): string {
  switch (dispositionKey(disposition)) {
    case "escalated":
      return "bg-n-11";
    case "failed":
      return "bg-n-9";
    case "resolved":
      return "bg-n-7";
    case "closed":
      return "bg-surface-4";
    default:
      return "bg-surface-3";
  }
}

export type DispositionSlice = {
  key: string;
  label: string;
  count: number;
  tone: string;
};

/** Outcome mix of the sampled window, densest first. Keyed by the canonical status key so two
 *  raw words that map onto one chip cannot double-count; the label keeps the backend's own word. */
export function dispositionTally(points: TelemetryPoint[]): DispositionSlice[] {
  const buckets = new Map<string, DispositionSlice>();
  for (const point of points) {
    const key = dispositionKey(point.disposition);
    const existing = buckets.get(key);
    if (existing) {
      existing.count += 1;
      continue;
    }
    buckets.set(key, {
      key,
      label: dispositionLabel(point.disposition),
      count: 1,
      tone: dispositionTone(point.disposition),
    });
  }
  return [...buckets.values()].sort((a, b) => b.count - a.count);
}
```

---

### PATCH 3 — `components/nexus/blocks.tsx` (additive)

**Find this exact line** (unique in the file):

```tsx
export function Legend({ items }: { items: { label: string; strong?: boolean }[] }) {
```

**Insert the following immediately ABOVE it** (leave `Legend` and everything else untouched):

```tsx
/** A single achromatic series with an optional hover guide — same SVG idiom as LineChart
 *  (viewBox 0 0 100 100, preserveAspectRatio="none", non-scaling strokes).
 *
 *  Differences from LineChart, all deliberate:
 *   - one series instead of two, with the scale supplied by the caller (metricMax) so an
 *     all-zero window degrades to a flat baseline instead of NaN geometry;
 *   - sparse x-axis ticks, because one label per point is unreadable past ~30 points;
 *   - hover state is LIFTED to the caller, which keeps this module stateless;
 *   - markers are lines, never circles: preserveAspectRatio="none" stretches geometry
 *     horizontally, so a circle would render as an ellipse.
 *
 *  Requires values.length >= 2 (the caller gates with isPlottable). */
export function SeriesChart({
  values,
  max,
  ticks,
  hovered,
  onHover,
}: {
  values: number[];
  max: number;
  ticks: { index: number; label: string }[];
  hovered: number | null;
  onHover: (index: number | null) => void;
}) {
  const step = 100 / (values.length - 1);
  const y = (value: number) => 100 - (value / max) * 100;
  const line = values.map((value, index) => `${index * step},${y(value)}`).join(" ");
  const area = `0,100 ${line} 100,100`;
  const guideX = hovered === null ? 0 : hovered * step;

  return (
    <div>
      <div className="relative h-[220px] w-full" onMouseLeave={() => onHover(null)}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="h-full w-full"
          aria-hidden="true"
        >
          {[0, 25, 50, 75, 100].map((gridline) => (
            <line
              key={gridline}
              x1="0"
              x2="100"
              y1={gridline}
              y2={gridline}
              stroke="var(--stroke-subtle)"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <polygon points={area} fill="var(--n-12)" fillOpacity="0.06" />
          <polyline
            points={line}
            fill="none"
            stroke="var(--n-12)"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
          {hovered === null ? null : (
            <>
              <line
                x1={guideX}
                x2={guideX}
                y1="0"
                y2="100"
                stroke="var(--n-8)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
              <line
                x1={Math.max(0, guideX - 2)}
                x2={Math.min(100, guideX + 2)}
                y1={y(values[hovered]!)}
                y2={y(values[hovered]!)}
                stroke="var(--n-12)"
                strokeWidth="3"
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}
        </svg>
        {/* Equal-width hit cells: the SVG is stretched, so hover is resolved in DOM space. */}
        <div className="absolute inset-0 flex" aria-hidden="true">
          {values.map((_, index) => (
            <div key={index} className="h-full flex-1" onMouseEnter={() => onHover(index)} />
          ))}
        </div>
      </div>
      <div className="mt-sp-4 flex justify-between">
        {ticks.map((tick) => (
          <span key={tick.index} className="t-micro text-ink-5">
            {tick.label}
          </span>
        ))}
      </div>
    </div>
  );
}

```

> `cn` is already imported at the top of `blocks.tsx`; `SeriesChart` does not need it, and no new
> import is added to that file.

---

### PATCH 4 — NEW FILE `components/nexus/telemetry-timeline.tsx`

Create the file with exactly this content:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Card, CardHeader, EmptyState, Segmented } from "@/components/nexus/primitives";
import { SeriesChart } from "@/components/nexus/blocks";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getVerdictDistribution } from "@/lib/api/decisions.server";
import { analyticsKeys } from "@/lib/nexus/query-keys";
import { dispositionLabel } from "@/lib/nexus/call-view";
import { formatInteger } from "@/lib/nexus/format";
import {
  TELEMETRY_METRICS,
  averageOf,
  axisTicks,
  dispositionTally,
  dispositionTone,
  formatMetric,
  isPlottable,
  metricMax,
  metricUnit,
  metricValues,
  timelineSpan,
} from "@/lib/nexus/telemetry-view";
import type { TelemetryMetric } from "@/lib/nexus/telemetry-view";
import { cn } from "@/lib/utils";

/** Fixed readout row. Deliberately not a floating tooltip: the chart's coordinate space is
 *  stretched by preserveAspectRatio="none", and a static row cannot clip or overflow. */
function Readout({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="mt-sp-6 flex flex-wrap gap-x-sp-7 gap-y-sp-4 border-t border-stroke-subtle pt-sp-5">
      {items.map((item) => (
        <div key={item.label}>
          <p className="t-micro text-ink-5">{item.label}</p>
          <p className="t-ui mt-sp-2 text-ink-1">{item.value}</p>
        </div>
      ))}
    </div>
  );
}

/** The 50 most recent recorded sessions from /api/v1/telemetry/timeline.
 *
 *  This component adds NO network traffic: it reuses the exact query key Overview already uses
 *  for the verdict mix, so the two screens share one cache entry and one request. That is why
 *  queryKeys.supervision.telemetryTimeline stays unused — a second key would mean a second
 *  fetch of a byte-identical response. */
export function TelemetryTimeline() {
  const [metric, setMetric] = useState<TelemetryMetric>("duration");
  const [hovered, setHovered] = useState<number | null>(null);

  const telemetry = useQuery({
    queryKey: analyticsKeys.verdicts(),
    queryFn: () => getVerdictDistribution(),
  });

  /* Label round-trip: the house Segmented idiom is keyed by label, not id. */
  const control = (
    <Segmented
      items={TELEMETRY_METRICS.map((option) => option.label)}
      active={TELEMETRY_METRICS.find((option) => option.id === metric)!.label}
      onSelect={(label) => setMetric(TELEMETRY_METRICS.find((o) => o.label === label)!.id)}
    />
  );

  if (telemetry.isPending) return <CardSkeleton lines={6} />;

  if (telemetry.isError) {
    return <ErrorState error={telemetry.error} onRetry={() => void telemetry.refetch()} />;
  }

  const timeline = telemetry.data.timeline;

  if (!isPlottable(timeline)) {
    return (
      <Card>
        <CardHeader
          title="Session Telemetry"
          subtitle="Call length and peak frustration across the most recent sessions."
        />
        <div className="mt-sp-7">
          <EmptyState
            icon={Activity}
            title="Not enough telemetry"
            description="At least two recorded sessions are needed before a timeline can be drawn."
          />
        </div>
      </Card>
    );
  }

  const values = metricValues(timeline, metric);
  const max = metricMax(values);
  const ticks = axisTicks(timeline);
  const tally = dispositionTally(timeline);
  const point = hovered === null ? null : timeline[hovered]!;
  const scope = `the last ${formatInteger(timeline.length)} recorded sessions, oldest first`;

  /* Idle: the shape of the window. Hovered: BOTH series for that session, so switching the
   * plotted metric never hides the other number. */
  const readout =
    point === null
      ? [
          { label: "Sessions", value: formatInteger(timeline.length) },
          { label: "Average", value: formatMetric(metric, averageOf(values)) },
          { label: "Peak", value: formatMetric(metric, Math.max(...values)) },
          { label: "Window", value: timelineSpan(timeline) },
        ]
      : [
          { label: "Time", value: point.timestamp },
          { label: "Duration", value: formatMetric("duration", point.duration) },
          { label: "Frustration", value: formatMetric("frustration", point.frustration) },
          { label: "Outcome", value: dispositionLabel(point.disposition) },
        ];

  return (
    <Card>
      <CardHeader
        title="Session Telemetry"
        subtitle={`${metricUnit(metric)} across ${scope}.`}
        action={control}
      />

      <Readout items={readout} />

      <div className="mt-sp-7">
        <SeriesChart
          values={values}
          max={max}
          ticks={ticks}
          hovered={hovered}
          onHover={setHovered}
        />
      </div>

      {/* Outcome band — one segment per session, column-aligned with the series above, so the
          shape of the curve can be read against how those calls actually ended. */}
      <div
        className="mt-sp-6 flex gap-[2px]"
        onMouseLeave={() => setHovered(null)}
        aria-hidden="true"
      >
        {timeline.map((session, index) => (
          <span
            key={index}
            onMouseEnter={() => setHovered(index)}
            className={cn(
              "block h-[6px] flex-1 rounded-[1px] transition-opacity",
              dispositionTone(session.disposition),
              hovered === null || hovered === index ? "opacity-100" : "opacity-40",
            )}
          />
        ))}
      </div>

      <div className="mt-sp-5 flex flex-wrap items-center gap-x-sp-6 gap-y-sp-3">
        {tally.map((slice) => (
          <span key={slice.key} className="inline-flex items-center gap-sp-3">
            <span
              aria-hidden="true"
              className={cn("block h-[6px] w-[14px] rounded-[1px]", slice.tone)}
            />
            <span className="t-caption text-ink-4">{slice.label}</span>
            <span className="t-caption text-ink-2">{formatInteger(slice.count)}</span>
          </span>
        ))}
      </div>
    </Card>
  );
}
```

---

### PATCH 5 — `routes/analytics.tsx` (two insertions, nothing removed)

**5a — the import.** Find this exact line:

```tsx
import { HeroStat, StatCard, LineChart, Legend } from "@/components/nexus/blocks";
```

Insert immediately after it:

```tsx
import { TelemetryTimeline } from "@/components/nexus/telemetry-timeline";
```

**5b — the mount.** Find this exact block (the tail of the component, unique in the file):

```tsx
        </Card>
      </PageSection>
    </>
  );
}
```

Replace it with:

```tsx
        </Card>
      </PageSection>

      <PageSection>
        <TelemetryTimeline />
      </PageSection>
    </>
  );
}
```

> Placement note: `AnalyticsPage` early-returns while `trend` is pending or errored, so the new
> section renders only once the trend query has settled. That is the existing page contract and is
> left as-is — the telemetry card owns its own pending / error / empty states for its own query.

---

## §5 — Gates

Run from `Frontend/admin_dashboard/`. These are the same three gates every previous frontend phase
used. **No tests are added and none are run.**

```bash
npx prettier --write \
  src/lib/api/decisions.server.ts \
  src/lib/nexus/telemetry-view.ts \
  src/components/nexus/blocks.tsx \
  src/components/nexus/telemetry-timeline.tsx \
  src/routes/analytics.tsx

npx tsc --noEmit          # expect: 0 errors
npx eslint src            # expect: 0 errors (pre-existing warning count unchanged)
npm run build             # expect: success
```

Only the five listed files are passed to prettier. Never run it across the tree.

### Eyeball pass (admin dev server on :8081)

1. `/analytics` → a **Session Telemetry** card appears below Volume Trend.
2. Header shows `Call length (mm:ss) across the last 50 recorded sessions, oldest first.`
3. Idle readout: Sessions `50` · Average `mm:ss` · Peak `mm:ss` · Window `HH:MM:SS → HH:MM:SS`.
4. Sweep the plot → the vertical guide follows the cursor and the readout switches to
   Time / Duration / Frustration / Outcome for that one session. Leave the card → it reverts.
5. Flip `Segmented` to **Frustration** → the curve rescales, the subtitle becomes
   `Peak frustration score across …`, values render as `0.82`-style two-decimals.
6. The outcome band under the chart dims to 40% except the hovered column; the legend beneath
   tallies the window (with 129 sessions live, the 50-session sample should be dominated by
   `Escalated` and `Abandoned`).
7. `/overview` → verdict mix cards are **unchanged**. Navigating `/overview` → `/analytics`
   fires **no second request** to `/api/v1/telemetry/timeline` (Network tab: one call, shared cache).

---

## §6 — Invariants this bundle must not break

Expressed as invariants, not literals, so a data change never invalidates the check.

1. `overview.tsx` is **byte-identical** before and after.
2. No `.py` file, CI file, Dockerfile, Makefile, lockfile or manifest is touched.
3. `status.ts` is untouched; its key count is unchanged.
4. `git diff --stat` lists **exactly five** paths, all under `Frontend/admin_dashboard/src/`.
5. Requests to `/api/v1/telemetry/timeline` per full dashboard session are **unchanged** (the new
   card shares Overview's cache entry).
6. Zero new npm dependencies; `package.json` and the lockfile are untouched.
7. Every colour is an existing token or CSS var (`var(--n-8)`, `var(--n-12)`, `var(--stroke-subtle)`,
   `bg-n-7/9/11`, `bg-surface-3/4`). No hex, no rgb, no new token.
8. Every timestamp shown is the backend's own `%H:%M:%S` string. No `new Date(...)` anywhere in the
   new code.
9. Existing `LineChart`, `BarChart`, `Legend`, `HeroStat`, `StatCard`, `StatGrid` signatures are
   unchanged.
10. The agent worker, LiveKit path, and every backend behaviour are outside this diff entirely.


What the two routes actually do — overview.tsx calls getVerdictDistribution() and touches exactly one field: const mix = verdicts.data.verdict_distribution. The 50 timeline points are fetched, decoded by response.json(), and dropped on every Overview visit. And analytics.tsx does own a real LineChart, but it plots /analytics/trend daily buckets ({day, current, previous}) — a different dataset at a different granularity, not a duplicate. So the gap is real, and it's a pure display gap: the data is already paid for.
How I fixed it. Five frontend files, zero new network requests:
Widened the wire type in decisions.server.ts instead of adding a second server function — a new getTelemetryTimeline() would have meant a second round-trip to the identical URL. The generic now describes what the endpoint always sent.
Reused Overview's cache key (analyticsKeys.verdicts()) so the two screens share one entry and one request. queryKeys.supervision.telemetryTimeline stays unused on purpose — a second key means a second fetch of byte-identical bytes.
Mounted on Analytics, left overview.tsx byte-identical. Overview is a density-first stat grid; dropping a 220px chart into it would have meant re-flowing a screen that already works.
One metric at a time, not two y-axes. Duration (seconds) and frustration (a small float) share no scale — a dual axis would have been a chart that lies. Instead a Segmented switch plots one, and the hover readout always shows both values for that session, so nothing is hidden.
Markers are lines, never circles. The house SVG idiom uses preserveAspectRatio="none", which stretches geometry horizontally — a circle would render as an ellipse. Hover state is lifted to the caller so blocks.tsx stays stateless.
Plus an outcome band under the curve, column-aligned per session, so the shape of the curve reads against how those calls actually ended.
Two things worth flagging: timestamp is a bare %H:%M:%S wall-clock string with no date part, so it's echoed verbatim and never parsed as a Date. And I floored the chart scale at 1 — the existing LineChart divides by Math.max(...values) * 1.08, which silently renders NaN geometry on an all-zero window. I logged that as debt rather than fixing it, since it was outside this bundle.
Boundaries held: no .py, no CI, no Makefile/Dockerfile, no tests, no package.json, no new colour or token, status.ts untouched.
The status report is deliberately honest rather than flattering. The headline is that the dashboard is wired end-to-end — 16/16 tabs on real data, 48/48 routes reachable — and the remaining distance is short and specific: two fake sidebar badges hardcoded in nav.ts (tickets: 42, callbacks: 7, rendered straight through to users as if live), one permanently dead "Subscriptions" card on Customers, two off-system shadcn-token error screens in __root.tsx, and a password-change flow whose endpoints exist with no screen. I also listed every file I have not opened, so the report's silence isn't mistaken for a clean bill of health.