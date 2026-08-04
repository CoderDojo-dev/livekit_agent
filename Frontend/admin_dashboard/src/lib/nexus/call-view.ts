import { formatBusinessTime } from "@/lib/nexus/callback-view";
import { formatDuration } from "@/lib/nexus/format";
import type { CallSessionRow, SentimentRow, TranscriptTurnRow } from "@/lib/api/sessions.server";

/** F7 — total mapping onto the canonical status truth table. Never returns undefined. */
export function dispositionKey(disposition: string | null): string {
  switch (disposition) {
    case "resolved":
      return "resolved";
    case "escalated":
      return "escalated";
    case "dropped":
      return "failed";
    case "abandoned":
      return "closed";
    default:
      return "in_progress";
  }
}

/** Human label, preserving the raw backend word even when it maps onto another chip. */
export function dispositionLabel(disposition: string | null): string {
  if (!disposition) return "In progress";
  return disposition.charAt(0).toUpperCase() + disposition.slice(1);
}

/** F5 — index alone is NOT unique; speaker disambiguates caller/agent at the same index. */
export function turnKey(turn: TranscriptTurnRow): string {
  return `${turn.index}-${turn.speaker}`;
}

/** F6 — sparse by design; a miss means "not measured", not "neutral". */
export function sentimentByIndex(samples: SentimentRow[]): Map<number, SentimentRow> {
  const map = new Map<number, SentimentRow>();
  for (const sample of samples) map.set(sample.index, sample);
  return map;
}

/** Existing achromatic tokens only. No new colours, no hex. */
export function sentimentTone(label: string | null): string {
  switch (label) {
    case "angry":
      return "bg-n-11";
    case "negative":
      return "bg-n-9";
    case "positive":
      return "bg-n-7";
    default:
      return "bg-surface-3";
  }
}

export function durationLabel(seconds: number | null): string {
  return seconds === null || seconds === undefined ? "\u2014" : formatDuration(seconds);
}

/** F3 — no local string in this payload, so we convert into the BUSINESS zone. */
export function callTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone ?? "UTC");
}

/** F10 — anonymous callers are normal. Never render "null null". */
export function callerName(row: CallSessionRow): string {
  return row.customer_name?.trim() || "Unknown caller";
}

export function frustrationLabel(score: number | null): string {
  return score === null || score === undefined ? "\u2014" : score.toFixed(1);
}
