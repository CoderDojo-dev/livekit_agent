// Feature 13 — escalations & human handoff. Pure functions, no JSX, no network.
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
