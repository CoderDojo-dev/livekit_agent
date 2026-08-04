// Feature 8 — decisions & requested-actions ledger. Pure functions, no JSX, no network.
import type { StatusKey } from "@/lib/nexus/status";
import type { Decision, Verdict } from "@/lib/api/decisions.server";

/**
 * G1 — the four-way action status total mapping. The ActionLedger status vocabulary is
 * (pending, succeeded, failed, retrying). Against status.ts:
 *   pending  -> pending   (exact)
 *   succeeded-> resolved  (terminal-success tone; disc / low / soft)
 *   failed   -> failed    (exact)
 *   retrying -> processing(in-flight, attempt_count >= 1; half / medium / soft)
 * queued was rejected for retrying: queued implies never-attempted.
 * Returns open on unknown so a StatusChip never renders a blank cell.
 */
export function actionStatusKey(status: DecisionActionStatus): StatusKey {
  switch (status) {
    case "succeeded":
      return "resolved";
    case "retrying":
      return "processing";
    case "pending":
      return "pending";
    case "failed":
      return "failed";
    default:
      return "open";
  }
}

type DecisionActionStatus = "pending" | "succeeded" | "failed" | "retrying";

/** G2 — verdicts are decision outcomes, not lifecycle statuses. Token display; never a chip. */
export function verdictLabel(v: Verdict): string {
  return v.charAt(0).toUpperCase() + v.slice(1).toLowerCase();
}

/** G2 — ESCALATE is the visually-distinct verdict; strong Token. */
export function isEscalate(v: Verdict): boolean {
  return v === "ESCALATE";
}

/**
 * G3 — business timezone is Africa/Tunis (CALLBACK_TIMEZONE); created_at is tz-aware UTC.
 * Intl.DateTimeFormat with an explicit timeZone. No getDay/getHours/toLocaleString.
 */
const INSTANT_FMT = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Tunis",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatInstant(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return INSTANT_FMT.format(date);
}

/** G/5.3 — the Actions column: "3 actions · 1 failed", or "No actions" when empty. */
export function actionRollup(d: Decision): string {
  if (d.actions.length === 0) return "No actions";
  const failed = d.actions.filter((a) => a.status === "failed").length;
  return `${d.actions.length} actions · ${failed} ${failed === 1 ? "failure" : "failures"}`;
}

/** G/5.3 — any child failed; drives row emphasis. */
export function hasFailure(d: Decision): boolean {
  return d.actions.some((a) => a.status === "failed");
}

/** G/5.3 — client-side search over action, rule_id, justification, session_id. */
export function decisionMatches(d: Decision, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  return (
    d.action.toLowerCase().includes(needle) ||
    d.rule_id.toLowerCase().includes(needle) ||
    d.justification.toLowerCase().includes(needle) ||
    d.session_id.toLowerCase().includes(needle)
  );
}

/** G/5.3 — truncate justification / error_message in cells; full text stays in the modal. */
export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}\u2026`;
}

/** G10 — verdict distribution, labelled honestly as "last 100 decisions". */
export function distributionTotals(
  dist: { authorized: number; refused: number; escalated: number } | undefined,
): number {
  if (!dist) return 0;
  return dist.authorized + dist.refused + dist.escalated;
}
