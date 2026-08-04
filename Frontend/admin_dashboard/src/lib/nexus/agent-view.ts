import type { AgentActivityRow } from "@/lib/api/agents.server";
import { AGENT_CATALOG, type AgentCatalogEntry } from "@/lib/nexus/agent-catalog";

export type AgentRow = {
  className: string;
  label: string;
  catalog: AgentCatalogEntry | null;
  turns: number;
  sessions: number;
  lastSeen: string | null;
  turnShare: number;
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

/** Union of the static catalog and everything actually observed. */
export function mergeAgentRows(observed: AgentActivityRow[], totalTurns: number): AgentRow[] {
  const byClass = new Map<string, AgentActivityRow>();
  for (const row of observed) byClass.set(row.agent, row);

  const seen = new Set<string>();
  const rows: AgentRow[] = [];

  for (const entry of AGENT_CATALOG) {
    const hit = byClass.get(entry.className);
    seen.add(entry.className);
    rows.push({
      className: entry.className,
      label: entry.label,
      catalog: entry,
      turns: hit?.turns ?? 0,
      sessions: hit?.sessions ?? 0,
      lastSeen: hit?.last_seen ?? null,
      turnShare: totalTurns > 0 ? (hit?.turns ?? 0) / totalTurns : 0,
    });
  }

  for (const row of observed) {
    if (seen.has(row.agent)) continue;
    rows.push({
      className: row.agent,
      label: humanizeClassName(row.agent),
      catalog: null,
      turns: row.turns,
      sessions: row.sessions,
      lastSeen: row.last_seen,
      turnShare: totalTurns > 0 ? row.turns / totalTurns : 0,
    });
  }

  return rows.sort((a, b) => b.turns - a.turns);
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
