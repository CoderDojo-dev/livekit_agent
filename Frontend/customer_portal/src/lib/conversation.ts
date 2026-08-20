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

export type CadenceTick = { x: number; agent: boolean };

/**
 * Tick positions for the conversation-cadence strip, 0..1 across the width.
 *
 * Two modes, and the caller is told which one it got, because they say
 * different things:
 *
 *   timed: true  - every turn carried a parseable `at` and the conversation
 *                  spans more than an instant, so x is the real time offset.
 *   timed: false - the timestamps are missing, unparseable, or all identical;
 *                  x falls back to turn ORDER. The sequence is still real
 *                  data, only the timing is unknown, and the label must say so
 *                  rather than implying a timeline that was never recorded.
 *
 * No interpolation, no smoothing, no invented points: one tick per turn.
 */
export function cadenceTicks(lines: ConversationTurn[]): {
  ticks: CadenceTick[];
  timed: boolean;
} {
  const stamps = lines.map((line) => (line.at ? Date.parse(line.at) : Number.NaN));
  const usable = stamps.length > 0 && stamps.every((value) => Number.isFinite(value));
  const first = stamps[0] ?? Number.NaN;
  const last = stamps[stamps.length - 1] ?? Number.NaN;
  const span = usable ? last - first : 0;
  // A negative span means the turns arrived out of order; ordering by index is
  // the honest reading of that, not a mirrored chart.
  const timed = usable && span > 0;

  const ticks = lines.map((line, index) => ({
    x: timed
      ? ((stamps[index] as number) - first) / span
      : lines.length > 1
        ? index / (lines.length - 1)
        : 0,
    agent: line.speaker === "agent",
  }));
  return { ticks, timed };
}

/** Transcript lines for a detail payload, tolerating an absent array. */
export function turnLines(
  detail: Pick<ConversationDetail, "turns"> | null | undefined,
): ConversationTurn[] {
  return Array.isArray(detail?.turns) ? detail.turns : [];
}
