import { formatPhone } from "./format";
import type { Callback } from "@/lib/api/callbacks.server";

/** The five scopes. Each maps to one legal (status, overdue_only) pair — see F15. */
export type CallbackScope = "pending" | "overdue" | "completed" | "cancelled" | "all";

export const CALLBACK_SCOPES: Array<{ id: CallbackScope; label: string }> = [
  { id: "pending", label: "Pending" },
  { id: "overdue", label: "Overdue" },
  { id: "completed", label: "Completed" },
  { id: "cancelled", label: "Cancelled" },
  { id: "all", label: "All" },
];

export function scopeQuery(scope: CallbackScope): {
  status: "pending" | "completed" | "cancelled" | "";
  overdueOnly: boolean;
} {
  switch (scope) {
    case "pending":
      return { status: "pending", overdueOnly: false };
    case "overdue":
      return { status: "pending", overdueOnly: true };
    case "completed":
      return { status: "completed", overdueOnly: false };
    case "cancelled":
      return { status: "cancelled", overdueOnly: false };
    case "all":
    default:
      // Empty string == no WHERE clause server-side. Not a bug; the only way to list everything.
      return { status: "", overdueOnly: false };
  }
}

/**
 * Total mapping onto status.ts keys. StatusChip returns null for unknown keys, so an unmapped
 * value would render a blank cell (the Feature 1 defect). 'completed' and 'cancelled' do not
 * exist in the truth table; 'overdue' does, and carries exactly the right tone.
 */
export function callbackStatusKey(row: Pick<Callback, "status" | "overdue">): string {
  if (row.status === "pending") return row.overdue ? "overdue" : "pending";
  if (row.status === "completed") return "resolved";
  if (row.status === "cancelled") return "closed";
  return "closed";
}

/**
 * Format a UTC instant in the BUSINESS timezone.
 *
 * Callbacks carry no pre-formatted local string (unlike coverage_report), so conversion is
 * mandatory here — and it must target the business zone, not the browser's, or this page will
 * disagree with /availability. hourCycle h23 avoids the "24:00" that hour12:false can emit.
 * No getDay(), no getHours(), no toLocaleString().
 */
export function formatBusinessTime(iso: string | null, timeZone: string): string {
  if (!iso) return "\u2014";
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return "\u2014";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = `${get("weekday")} ${get("day")} ${get("month")}`.trim();
  const time = `${get("hour")}:${get("minute")}`;
  return day ? `${day} \u00b7 ${time}` : time;
}

/** Short form for dense cells: "03 Aug 09:00". */
export function formatBusinessDayTime(iso: string | null, timeZone: string): string {
  if (!iso) return "\u2014";
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return "\u2014";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")} ${get("month")} ${get("hour")}:${get("minute")}`;
}

export function callbackCustomer(row: Callback): { name: string; phone: string } {
  return {
    name: row.customer_name?.trim() || "Unknown caller",
    phone: row.customer_phone ? formatPhone(row.customer_phone) : "\u2014",
  };
}

/** priority_level is an unconstrained integer with no defined scale — show it, don't grade it. */
export function priorityLabel(level: number): string | null {
  if (!Number.isFinite(level) || level === 1) return null;
  return `P${level}`;
}

export function callbackMatches(row: Callback, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    row.customer_name,
    row.customer_phone,
    row.assigned_advisor_name,
    row.preferred_window,
    row.reason,
    row.outcome_note,
  ];
  return haystack.some((v) => (v ?? "").toLowerCase().includes(q));
}

/** The count the footer compares against, so truncation is visible (F14). */
export function scopeTotal(
  scope: CallbackScope,
  stats: { pending: number; overdue: number; completed: number } | undefined,
): number | null {
  if (!stats) return null;
  if (scope === "pending") return stats.pending;
  if (scope === "overdue") return stats.overdue;
  if (scope === "completed") return stats.completed;
  return null; // queue_stats does not count cancelled, and 'all' has no single counter
}
