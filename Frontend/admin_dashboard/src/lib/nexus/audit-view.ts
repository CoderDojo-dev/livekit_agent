import type { AuditEntry, IntegrityReport } from "@/lib/api/audit.server";

/** "billing.accounts->crm.customers" -> "billing.accounts → crm.customers" */
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

/** ISO instant -> "2026-08-03 14:32" in a locale-independent form. */
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
