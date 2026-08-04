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

/** Sum of open invoice amounts, for the panel's summary line. */
export function outstandingTotal(invoices: Array<{ amount: number }>): number {
  return invoices.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
}
