import type { ServiceEvent } from "@/lib/api/customers.server";
import type { StatusKey } from "@/lib/nexus/status";

/** crm.customers.status -> canonical key. All three already exist in status.ts. */
export function customerStatusKey(status: string): StatusKey | null {
  switch (status) {
    case "active":
      return "active";
    case "suspended":
      return "suspended";
    case "closed":
      return "closed";
    default:
      return null;
  }
}

/** crm.subscriptions.status is UPPERCASE and has two keys status.ts does not know. */
export function subscriptionStatusKey(status: string): StatusKey | null {
  switch (status?.toUpperCase()) {
    case "ACTIVE":
      return "active";
    case "SUSPENDED":
      return "suspended";
    case "BLOCKED":
      return "disabled";
    case "TERMINATED":
      return "closed";
    default:
      return null;
  }
}

/** billing.invoices.status has seven values; status.ts knows three. */
export function invoiceStatusKey(status: string): StatusKey | null {
  switch (status?.toLowerCase()) {
    case "draft":
      return "draft";
    case "issued":
      return "pending";
    case "paid":
      return "paid";
    case "partial":
      return "in_progress";
    case "overdue":
      return "overdue";
    case "disputed":
      return "escalated";
    case "void":
      return "archived";
    default:
      return null;
  }
}

const PAYMENT_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  succeeded: "paid",
  failed: "failed",
  refunded: "refunded",
};

export function paymentStatusKey(status: string): StatusKey {
  return PAYMENT_STATUS[status] ?? "draft";
}

const PAYMENT_PLAN_STATUS: Record<string, StatusKey> = {
  proposed: "draft",
  active: "active",
  completed: "resolved",
  defaulted: "failed",
  cancelled: "closed",
};

export function paymentPlanStatusKey(status: string): StatusKey {
  return PAYMENT_PLAN_STATUS[status] ?? "draft";
}

export function consentStatusKey(granted: boolean): StatusKey {
  return granted ? "enabled" : "disabled";
}

const PAYMENT_METHOD_LABEL: Record<string, string> = {
  card: "Card",
  bank_transfer: "Bank transfer",
  wallet: "Wallet",
  voucher: "Voucher",
  cash: "Cash",
};

export function paymentMethodLabel(method: string): string {
  return PAYMENT_METHOD_LABEL[method] ?? method;
}

const CONSENT_TYPE_LABEL: Record<string, string> = {
  call_recording: "Call recording",
  data_processing: "Data processing",
  marketing: "Marketing",
};

export function consentTypeLabel(type: string): string {
  return CONSENT_TYPE_LABEL[type] ?? type;
}

const BALANCE_STATUS: Record<string, StatusKey> = {
  active: "active",
  expired: "inactive",
  suspended: "suspended",
};

export function balanceStatusKey(status: string): StatusKey {
  return BALANCE_STATUS[status] ?? "inactive";
}

const RECHARGE_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  completed: "resolved",
  failed: "failed",
};

const SIM_CASE_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  identity_verified: "in_progress",
  completed: "resolved",
  escalated: "escalated",
  rejected: "closed",
};

const SIM_ORDER_STATUS: Record<string, StatusKey> = {
  requested: "pending",
  shipped: "in_progress",
  activated: "active",
  cancelled: "closed",
};

const PROVISIONING_STATUS: Record<string, StatusKey> = {
  pending: "pending",
  in_progress: "in_progress",
  completed: "resolved",
  failed: "failed",
};

/**
 * Each source has its own lifecycle vocabulary; there is no shared enum.
 * Falls back to "open" so a StatusChip never renders blank — the precedent set by
 * decision-view.ts::actionStatusKey.
 */
export function serviceEventStatusKey(event: ServiceEvent): StatusKey {
  switch (event.source) {
    case "recharge":
      return RECHARGE_STATUS[event.status] ?? "open";
    case "sim_case":
      return SIM_CASE_STATUS[event.status] ?? "open";
    case "sim_order":
      return SIM_ORDER_STATUS[event.status] ?? "open";
    case "provisioning":
      return PROVISIONING_STATUS[event.status] ?? "open";
    default:
      return "open";
  }
}

const BALANCE_TYPE_LABEL: Record<string, string> = {
  main: "Main credit",
  data: "Data",
  voice: "Voice",
  sms: "SMS",
};

export function balanceTypeLabel(type: string): string {
  return BALANCE_TYPE_LABEL[type] ?? type;
}

const SIM_ACTION_LABEL: Record<string, string> = {
  BLOCK: "SIM block",
  UNBLOCK: "SIM unblock",
  UNLOCK_PUK: "PUK unlock",
  REACTIVATE: "SIM reactivation",
};

const PROVISIONING_ACTION_LABEL: Record<string, string> = {
  CHANGE_PLAN: "Plan change",
  ACTIVATE_ROAMING: "Roaming activation",
};

const SIM_TYPE_LABEL: Record<string, string> = {
  physical: "Physical SIM",
  esim: "eSIM",
};

/** One-line title per event; never blank, always derived from a real column. */
export function serviceEventTitle(event: ServiceEvent): string {
  switch (event.source) {
    case "recharge":
      return "Top-up";
    case "sim_case":
      return SIM_ACTION_LABEL[event.action] ?? event.action;
    case "sim_order":
      return `SIM order · ${SIM_TYPE_LABEL[event.sim_type] ?? event.sim_type}`;
    case "provisioning":
      return PROVISIONING_ACTION_LABEL[event.action_type] ?? event.action_type;
    default:
      return "Service action";
  }
}

const CHANGED_BY_LABEL: Record<string, string> = {
  agent: "Agent",
  self_service: "Self-service",
  advisor: "Advisor",
};

export function changedByLabel(changedBy: string): string {
  return CHANGED_BY_LABEL[changedBy] ?? changedBy;
}

const RECHARGE_CHANNEL_LABEL: Record<string, string> = {
  app: "App",
  web: "Web",
  ussd: "USSD",
  scratch_card: "Scratch card",
  agent: "Agent",
};

export function rechargeChannelLabel(channel: string): string {
  return RECHARGE_CHANNEL_LABEL[channel] ?? channel;
}

const LANGUAGE_LABEL: Record<string, string> = {
  fr: "FR",
  ar: "AR",
  en: "EN",
};

export function languageLabel(code: string | null | undefined): string {
  if (!code) return "\u2014";
  return LANGUAGE_LABEL[code.toLowerCase()] ?? code.toUpperCase();
}

/**
 * Money formatter for billing amounts.
 *
 * Deliberately NOT format.ts `formatCurrency`, which expects CENTS. Invoice amounts are
 * Numeric(12,2) decimal units, so formatCurrency would render 120.50 TND as 1.21.
 */
export function formatAmount(amount: number, currency = "TND"): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return "\u2014";
  return `${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;
}

/** Inclusive 1-based range for the footer, correct on the final partial page. */
export function pageRange(
  offset: number,
  limit: number,
  total: number,
): { from: number; to: number } {
  if (total === 0) return { from: 0, to: 0 };
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return { from, to };
}

export function hasPrevious(offset: number): boolean {
  return offset > 0;
}

export function hasNext(offset: number, limit: number, total: number): boolean {
  return offset + limit < total;
}

/**
 * Invoice statuses that represent money someone still owes.
 *
 * `customer_360` returns every invoice whose status is not `paid` (repositories.py,
 * `open_invoices`), which sweeps in `draft` (never issued to the customer) and `void`
 * (cancelled). Neither is owed by anybody, so neither belongs in a money total.
 */
const OWED_STATUSES = new Set<string>(["issued", "partial", "overdue", "disputed"]);

/**
 * Sum of the balance still owed across invoices in an owed status, for the panel's
 * summary line. FEATURE_21 — sums `outstanding` (remaining balance), not `amount`
 * (face value); on a partial invoice those differ by whatever has already been paid.
 */
export function unpaidTotal(invoices: Array<{ outstanding: number; status: string }>): number {
  return invoices.reduce(
    (sum, i) =>
      OWED_STATUSES.has(i.status?.toLowerCase() ?? "") ? sum + (Number(i.outstanding) || 0) : sum,
    0,
  );
}
