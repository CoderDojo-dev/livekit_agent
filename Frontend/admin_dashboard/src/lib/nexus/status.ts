// Chapter 1.7 — the canonical status truth table. No status exists outside it.
export type StatusShape =
  | "disc"
  | "ring"
  | "half"
  | "triangle"
  | "square"
  | "bar";
export type StatusLevel = "critical" | "high" | "medium" | "low" | "inert";
export type StatusContainer = "flat" | "soft" | "outline" | "inverted";

export type StatusDefinition = {
  shape: StatusShape;
  level: StatusLevel;
  container: StatusContainer;
  label: string;
};

export const STATUS: Record<string, StatusDefinition> = {
  active: { shape: "disc", level: "high", container: "soft", label: "Active" },
  inactive: {
    shape: "bar",
    level: "inert",
    container: "flat",
    label: "Inactive",
  },
  invited: {
    shape: "ring",
    level: "medium",
    container: "outline",
    label: "Invited",
  },
  suspended: {
    shape: "bar",
    level: "critical",
    container: "outline",
    label: "Suspended",
  },
  pending: {
    shape: "ring",
    level: "medium",
    container: "outline",
    label: "Pending",
  },
  open: { shape: "ring", level: "high", container: "outline", label: "Open" },
  in_progress: {
    shape: "half",
    level: "medium",
    container: "soft",
    label: "In Progress",
  },
  resolved: {
    shape: "disc",
    level: "low",
    container: "soft",
    label: "Resolved",
  },
  closed: {
    shape: "square",
    level: "inert",
    container: "flat",
    label: "Closed",
  },
  escalated: {
    shape: "triangle",
    level: "critical",
    container: "inverted",
    label: "Escalated",
  },
  indexed: {
    shape: "disc",
    level: "high",
    container: "soft",
    label: "Indexed",
  },
  processing: {
    shape: "half",
    level: "medium",
    container: "soft",
    label: "Processing",
  },
  failed: {
    shape: "triangle",
    level: "critical",
    container: "outline",
    label: "Failed",
  },
  queued: {
    shape: "ring",
    level: "medium",
    container: "outline",
    label: "Queued",
  },
  paid: { shape: "disc", level: "high", container: "soft", label: "Paid" },
  overdue: {
    shape: "triangle",
    level: "critical",
    container: "inverted",
    label: "Overdue",
  },
  refunded: {
    shape: "square",
    level: "low",
    container: "flat",
    label: "Refunded",
  },
  online: { shape: "disc", level: "high", container: "soft", label: "Online" },
  away: { shape: "ring", level: "medium", container: "outline", label: "Away" },
  offline: {
    shape: "bar",
    level: "inert",
    container: "flat",
    label: "Offline",
  },
  on_call: {
    shape: "half",
    level: "high",
    container: "soft",
    label: "On call",
  },
  draft: { shape: "ring", level: "low", container: "outline", label: "Draft" },
  published: {
    shape: "disc",
    level: "high",
    container: "soft",
    label: "Published",
  },
  archived: {
    shape: "square",
    level: "inert",
    container: "flat",
    label: "Archived",
  },
  enabled: {
    shape: "disc",
    level: "high",
    container: "soft",
    label: "Enabled",
  },
  disabled: {
    shape: "bar",
    level: "inert",
    container: "flat",
    label: "Disabled",
  },
};

export type StatusKey = keyof typeof STATUS;
