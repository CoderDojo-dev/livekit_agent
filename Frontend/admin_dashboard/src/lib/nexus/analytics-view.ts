import { formatPercent } from "@/lib/nexus/format";
import type { KpiBundle, TrendPoint, VerdictDistribution } from "@/lib/api/analytics.server";

/** Ratios arrive as 0..1 from `_ratio`. formatPercent's contract is the same scale (G15). */
export function formatRatio(ratio: number): string {
  return formatPercent(ratio, 1);
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
export function deltaPoints(
  current: number,
  previous: number,
  previousTotal: number,
): number | undefined {
  if (!previousTotal) return undefined;
  return Number(((current - previous) * 100).toFixed(1));
}

/** "2026-08-03" -> "Aug 3". Date-only string, parsed as UTC-safe parts, never `new Date(s)`. */
export function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-").map(Number);
  const MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
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
