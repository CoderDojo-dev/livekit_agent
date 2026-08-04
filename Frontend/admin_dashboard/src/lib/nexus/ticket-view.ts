import { formatBusinessTime } from "@/lib/nexus/callback-view";

/** F5 — identity mapping: the DB CheckConstraint already guarantees these five keys exist
 *  in status.ts. The function exists so the invariant is named, and so an out-of-band value
 *  can never render a blank chip (the defect Features 1, 3 and 4 each hit). */
export function ticketStatusKey(status: string | null): string {
  switch (status) {
    case "open":
    case "in_progress":
    case "pending":
    case "resolved":
    case "closed":
      return status;
    default:
      return "open";
  }
}

/**
 * F6 — named priorities map onto the three lawful PriorityMeter levels.
 * The shipped PriorityMeter accepts only "high" | "medium" | "low" (no critical/inert).
 * urgent and high both render as high; NULL (untriaged) returns null so the route can show a
 * muted dash rather than implying "low" — "not triaged" and "judged low" are different facts.
 */
export function ticketPriorityLevel(priority: string | null): "high" | "medium" | "low" | null {
  switch (priority) {
    case "urgent":
    case "high":
      return "high";
    case "medium":
      return "medium";
    case "low":
      return "low";
    default:
      return null;
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  network_complaint: "Network",
  formal_complaint: "Complaint",
  technical: "Technical",
  billing: "Billing",
  other: "Other",
};

export function categoryLabel(category: string | null): string {
  if (!category) return "Other";
  return CATEGORY_LABELS[category] ?? category;
}

export const STATUS_ORDER = ["open", "in_progress", "pending", "resolved", "closed"] as const;

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

/** F9 — counts omit zero-row statuses; never render a blank. */
export function statusCount(counts: Record<string, number> | undefined, status: string): number {
  return counts?.[status] ?? 0;
}

/** F16 — subject is nullable and truncated at 255 upstream. */
export function ticketSubject(subject: string | null): string {
  return subject?.trim() || "\u2014";
}

/** F15 — tickets can have no customer. */
export function ticketCustomer(name: string | null): string {
  return name?.trim() || "Unknown customer";
}

/** F14 — no local string in this payload; convert into the BUSINESS zone. */
export function ticketTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone ?? "UTC");
}
