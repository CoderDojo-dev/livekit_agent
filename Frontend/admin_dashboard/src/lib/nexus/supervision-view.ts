// Wiring for /api/v1/policy/verdicts and /api/v1/actions. Pure functions, no JSX, no network.
import type { LedgerActionStatus, SessionVerdict } from "@/lib/api/supervision.server";

/**
 * verdicts() returns `verdict` as a raw string, not the Verdict enum decisions.server.ts
 * declares, so it is normalised here rather than cast. PolicyVerdict.verdict is stored
 * uppercase (CheckConstraint); display is title case, matching verdictLabel() in
 * decision-view.ts without importing a type that does not fit this projection.
 */
export function sessionVerdictLabel(verdict: string): string {
  if (!verdict) return "\u2014";
  return verdict.charAt(0).toUpperCase() + verdict.slice(1).toLowerCase();
}

/** ESCALATE is the visually-distinct verdict — strong Token, same rule as decision-view.ts. */
export function isEscalateVerdict(verdict: string): boolean {
  return verdict.toUpperCase() === "ESCALATE";
}

/** REFUSED and ESCALATE are the two outcomes a supervisor scans a call for. */
export function isBlockingVerdict(verdict: string): boolean {
  const v = verdict.toUpperCase();
  return v === "REFUSED" || v === "ESCALATE";
}

/**
 * The /actions projection carries no attempt_count and no error_message, so the roll-up can
 * only honestly report the count. Never render "0 failures" from a list the server already
 * filtered to one status.
 */
export function actionScopeLabel(status: LedgerActionStatus, count: number): string {
  return `${count} ${status} ${count === 1 ? "action" : "actions"}`;
}

/** Backend order is chronological (created_at ASC); the step number conveys it without a time. */
export function verdictSequence(
  verdicts: SessionVerdict[],
): Array<SessionVerdict & { step: number }> {
  return verdicts.map((v, i) => ({ ...v, step: i + 1 }));
}
