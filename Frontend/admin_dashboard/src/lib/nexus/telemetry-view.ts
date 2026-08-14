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
