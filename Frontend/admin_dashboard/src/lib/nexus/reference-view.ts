import type { CatalogKind } from "@/lib/api/reference.server";

/*
 * Tab order is commercial-first.
 *
 * Plans leads because it is the catalog an operator reaches for most and the one a caller asks
 * about; error messages moved to the end because they are consulted when something has already
 * gone wrong, which is the rarer errand. The route's default selection follows this array's
 * first entry, so the two can never disagree.
 */
export const CATALOG_TABS: Array<{ value: CatalogKind; label: string }> = [
  { value: "products", label: "Plans" },
  { value: "recharges", label: "Recharges" },
  { value: "areas", label: "Geo areas" },
  { value: "errors", label: "Error messages" },
];

/** The tab selected on arrival. Derived, so reordering CATALOG_TABS re-points it automatically. */
export const DEFAULT_CATALOG: CatalogKind = CATALOG_TABS[0]!.value;

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
