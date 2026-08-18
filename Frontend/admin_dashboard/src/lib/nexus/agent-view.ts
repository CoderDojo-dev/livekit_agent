import type { AgentActivityPersona, AgentDailyPoint } from "@/lib/api/agents.server";
import { AGENT_CATALOG, type AgentCatalogEntry } from "@/lib/nexus/agent-catalog";

export type AgentRow = {
  className: string;
  label: string;
  catalog: AgentCatalogEntry | null;
  attributedCalls: number;
  completedCalls: number;
  attributedCallDurationSeconds: number;
  averageCompletedCallDurationSeconds: number | null;
  providerInputTokens: number | null;
  providerOutputTokens: number | null;
  tokenEventCount: number;
  lastObservedAt: string | null;
  attributionShare: number;
  daily: AgentDailyPoint[];
};

const BY_CLASS = new Map(AGENT_CATALOG.map((entry) => [entry.className, entry]));

/**
 * Split a Python class name into words: "AccountServicesAgent" -> "Account Services".
 * Used ONLY for class names absent from the catalog, so drift is legible
 * rather than raw (Cookbook 12 §0.3).
 */
export function humanizeClassName(className: string): string {
  const withoutSuffix = className.replace(/Agent$/, "");
  const spaced = withoutSuffix.replace(/([a-z0-9])([A-Z])/g, "$1 $2").trim();
  return spaced || className;
}

export function agentLabel(className: string): string {
  return BY_CLASS.get(className)?.label ?? humanizeClassName(className);
}

export function isKnownAgent(className: string): boolean {
  return BY_CLASS.has(className);
}

/** UTC day keys for a window: midnight of the oldest day through day `days - 1`. */
function denseDayKeys(from: string, days: number): string[] {
  const start = new Date(from);
  const keys: string[] = [];
  for (let offset = 0; offset < days; offset += 1) {
    keys.push(new Date(start.getTime() + offset * 86_400_000).toISOString().slice(0, 10));
  }
  return keys;
}

function emptyDay(day: string): AgentDailyPoint {
  return {
    day,
    attributed_calls: 0,
    attributed_call_duration_seconds: 0,
    provider_input_tokens: null,
    provider_output_tokens: null,
  };
}

/** Union of the static catalog and everything actually observed. */
export function mergeAgentRows(
  observed: AgentActivityPersona[],
  totalAttributions: number,
  window: { from: string; days: number },
): AgentRow[] {
  const byClass = new Map(observed.map((row) => [row.persona, row]));
  const dayKeys = denseDayKeys(window.from, window.days);
  const rows: AgentRow[] = [];

  for (const entry of AGENT_CATALOG) {
    const hit = byClass.get(entry.className);
    rows.push({
      className: entry.className,
      label: entry.label,
      catalog: entry,
      attributedCalls: hit?.attributed_calls ?? 0,
      completedCalls: hit?.completed_calls ?? 0,
      attributedCallDurationSeconds: hit?.attributed_call_duration_seconds ?? 0,
      averageCompletedCallDurationSeconds: hit?.average_completed_call_duration_seconds ?? null,
      providerInputTokens: hit?.provider_input_tokens ?? null,
      providerOutputTokens: hit?.provider_output_tokens ?? null,
      tokenEventCount: hit?.token_event_count ?? 0,
      lastObservedAt: hit?.last_observed_at ?? null,
      attributionShare:
        totalAttributions > 0 ? (hit?.attributed_calls ?? 0) / totalAttributions : 0,
      daily: hit?.daily ?? dayKeys.map(emptyDay),
    });
  }

  const seen = new Set(AGENT_CATALOG.map((entry) => entry.className));
  for (const row of observed) {
    if (seen.has(row.persona)) continue;
    rows.push({
      className: row.persona,
      label: humanizeClassName(row.persona),
      catalog: null,
      attributedCalls: row.attributed_calls,
      completedCalls: row.completed_calls,
      attributedCallDurationSeconds: row.attributed_call_duration_seconds,
      averageCompletedCallDurationSeconds: row.average_completed_call_duration_seconds,
      providerInputTokens: row.provider_input_tokens,
      providerOutputTokens: row.provider_output_tokens,
      tokenEventCount: row.token_event_count,
      lastObservedAt: row.last_observed_at,
      attributionShare: totalAttributions > 0 ? row.attributed_calls / totalAttributions : 0,
      daily: row.daily,
    });
  }

  return rows.sort(
    (a, b) =>
      b.attributedCalls - a.attributedCalls ||
      b.attributedCallDurationSeconds - a.attributedCallDurationSeconds,
  );
}

/**
 * Absolute instant, no relative-time arithmetic and no locale weekday lookup.
 * Cookbook 3/8/9 rule: never getDay()/getHours() on a backend instant.
 */
export function formatLastSeen(iso: string | null): string {
  if (!iso) return "\u2014";
  const datePart = iso.slice(0, 10);
  const timePart = iso.slice(11, 16);
  return timePart ? `${datePart} ${timePart}` : datePart;
}

export function sharePercent(share: number): string {
  if (!Number.isFinite(share) || share <= 0) return "0%";
  const pct = share * 100;
  return pct < 1 ? "<1%" : `${Math.round(pct)}%`;
}

export function routesLabel(entry: AgentCatalogEntry | null): string {
  if (!entry) return "Unknown";
  if (entry.terminal) return "Terminal";
  if (entry.routes.length === 0) return "Specialist";
  return `Routes ${entry.routes.length}`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
}

export function providerTokenTotal(row: AgentRow): number | null {
  if (row.providerInputTokens === null && row.providerOutputTokens === null) {
    return null;
  }
  return (row.providerInputTokens ?? 0) + (row.providerOutputTokens ?? 0);
}

export function dailyTokenTotal(point: AgentDailyPoint): number | null {
  if (point.provider_input_tokens === null && point.provider_output_tokens === null) {
    return null;
  }
  return (point.provider_input_tokens ?? 0) + (point.provider_output_tokens ?? 0);
}
