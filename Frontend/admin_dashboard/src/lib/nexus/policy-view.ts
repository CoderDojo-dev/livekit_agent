// Feature 7 — policies. Pure functions, no JSX, no network.
import type { StatusKey } from "@/lib/nexus/status";
import type { PolicyRule } from "@/lib/api/policies.server";

/** G2 — `active` is a boolean; both target keys already exist in status.ts. Avoid String(active). */
export function ruleStatusKey(active: boolean): StatusKey {
  return active ? "active" : "inactive";
}

/**
 * G3 — definition is variable-shape JSONB. Known keys humanise with one of three consistent unit
 * suffixes; unknown keys render their raw value with no invented unit.
 */
const UNIT_SUFFIX: Record<string, string> = {
  tnd: " TND",
  days: " days",
  per_year: "/year",
};

/** `max_payment_tnd` -> "Max payment" */
export function thresholdLabel(key: string): string {
  const label = key.replace(/_(tnd|days|per_year)$/, "").replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

/** Suffix-driven unit only; unknown keys get no unit. */
export function thresholdValue(key: string, value: number | string | boolean): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  const suffix = Object.entries(UNIT_SUFFIX).find(([suffixKey]) => key.endsWith(`_${suffixKey}`));
  return `${String(value)}${suffix ? suffix[1] : ""}`;
}

/** G3 — each entry renders as humanised label + value, stacked. Empty {} -> em-dash. */
export function definitionEntries(
  definition: Record<string, number | string | boolean>,
): Array<{ label: string; value: string }> {
  return Object.entries(definition).map(([key, value]) => ({
    label: thresholdLabel(key),
    value: thresholdValue(key, value),
  }));
}

/** G4 — enforced vs catalog is the honesty surface of the whole page. */
export function enforcementLabel(rule: PolicyRule): "Enforced" | "Catalog" {
  return rule.enforced ? "Enforced" : "Catalog";
}

/** G4/type-safety — never returns undefined; `[]` when absent. */
export function governedByList(rule: PolicyRule): string[] {
  return rule.enforced ? (rule.governed_by ?? []) : [];
}

/** Client-side search over rule id, description, domain. */
export function ruleMatches(rule: PolicyRule, query: string): boolean {
  if (!query.trim()) return true;
  const needle = query.toLowerCase();
  return (
    rule.rule_id.toLowerCase().includes(needle) ||
    (rule.description ?? "").toLowerCase().includes(needle) ||
    rule.domain.toLowerCase().includes(needle)
  );
}

/** G11 — group by domain preserving server order (domain, rule_id); no client re-sort. */
export function groupByDomain(rules: PolicyRule[]): Array<{ domain: string; rules: PolicyRule[] }> {
  const groups: Array<{ domain: string; rules: PolicyRule[] }> = [];
  for (const rule of rules) {
    const last = groups[groups.length - 1];
    if (last && last.domain === rule.domain) {
      last.rules.push(rule);
    } else {
      groups.push({ domain: rule.domain, rules: [rule] });
    }
  }
  return groups;
}
