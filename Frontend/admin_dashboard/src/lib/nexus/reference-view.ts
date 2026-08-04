import type { CatalogKind } from "@/lib/api/reference.server";

export const CATALOG_TABS: Array<{ value: CatalogKind; label: string }> = [
  { value: "errors", label: "Error messages" },
  { value: "products", label: "Plans" },
  { value: "recharges", label: "Recharges" },
  { value: "areas", label: "Geo areas" },
];

export const CATALOG_SUBTITLE: Record<CatalogKind, string> = {
  errors: "What the agent says to a caller when something fails, per language.",
  products: "The plan catalog the agent can offer and switch a subscriber to.",
  recharges: "Prepaid denominations and their bonus amounts.",
  areas: "Canonical Tunisian zones. Outages can only reference a zone listed here.",
};

/** active -> canonical status.ts key (Cookbook 7 mapping, unchanged). */
export function activeStatusKey(active: boolean): string {
  return active ? "active" : "inactive";
}

/**
 * Numeric(12,2) is DECIMAL UNITS, not cents.
 * format.ts formatCurrency() takes cents and must never be used here (Cookbook 11).
 */
export function formatAmount(value: number): string {
  return `${value.toFixed(2)} TND`;
}

const AREA_TYPE_LABEL: Record<string, string> = {
  governorate: "Governorate",
  delegation: "Delegation",
  locality: "Locality",
};

/** CheckConstraint allows three values; unknown passes through verbatim. */
export function areaTypeLabel(t: string): string {
  return AREA_TYPE_LABEL[t] ?? t;
}

/** Nullable Text columns: never render "null". */
export function orDash(v: string | null | undefined): string {
  return v && v.trim() ? v : "\u2014";
}
