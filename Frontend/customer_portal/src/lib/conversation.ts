/**
 * lib/conversation.ts - reconciles the one place where the me/* API uses a
 * single field name for two different shapes.
 *
 *   GET /me/conversations        -> ConversationSummary.turns : number  (a count)
 *   GET /me/conversations/{id}   -> ConversationDetail.turns  : Turn[]  (the transcript)
 *
 * Rendering the detail shape as a scalar produced
 * "[object Object],[object Object],..." on screen. Everything that needs "how
 * many turns" goes through turnCount() so the two shapes can never be confused
 * at a call site again.
 */
import type {
  ConversationDetail,
  ConversationSummary,
  ConversationTurn,
} from "./api/activity.server";

/** Turn count for either endpoint shape. Unknown or absent data counts as 0. */
export function turnCount(
  turns: ConversationSummary["turns"] | ConversationDetail["turns"] | null | undefined,
): number {
  if (Array.isArray(turns)) return turns.length;
  return typeof turns === "number" && Number.isFinite(turns) && turns > 0 ? Math.trunc(turns) : 0;
}

/** Transcript lines for a detail payload, tolerating an absent array. */
export function turnLines(
  detail: Pick<ConversationDetail, "turns"> | null | undefined,
): ConversationTurn[] {
  return Array.isArray(detail?.turns) ? detail.turns : [];
}
