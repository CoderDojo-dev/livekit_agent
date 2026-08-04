import type { Advisor, AdvisorStatus } from "@/lib/api/advisors.server";

/**
 * Map backend advisor state onto a key that exists in STATUS (status.ts).
 *
 * The backend emits available | busy | offline. STATUS contains none of the
 * first two, and StatusChip returns null for unknown keys — so passing the raw
 * value renders an empty cell. Employment state is checked first: a deactivated
 * advisor is never routable, whatever their presence flag says.
 */
export function advisorStatusKey(advisor: Pick<Advisor, "status" | "is_active">): string {
  if (!advisor.is_active) return "inactive";
  switch (advisor.status) {
    case "available":
      return "online";
    case "busy":
      return "on_call";
    case "offline":
      return "offline";
    default:
      return "offline";
  }
}

/** Labels for the status editor. Backend vocabulary, not chip vocabulary. */
export const ADVISOR_STATUS_OPTIONS: { value: AdvisorStatus; label: string }[] = [
  { value: "available", label: "Available" },
  { value: "busy", label: "Busy" },
  { value: "offline", label: "Offline" },
];

/** Human presence label for lines where a raw status read is wanted (Feature 9 team panel). */
export function advisorPresenceLabel(status: AdvisorStatus): string {
  switch (status) {
    case "available":
      return "Available now";
    case "busy":
      return "On a call";
    default:
      return "Offline";
  }
}

/** "1/2" — live load over configured capacity. */
export function advisorLoad(
  advisor: Pick<Advisor, "active_calls" | "max_concurrent_calls">,
): string {
  return `${advisor.active_calls}/${advisor.max_concurrent_calls}`;
}

/** Phone first, SIP as fallback. Service logic guarantees at least one exists. */
export function advisorContact(advisor: Pick<Advisor, "phone_e164" | "sip_uri">): string | null {
  return advisor.phone_e164 || advisor.sip_uri || null;
}

/** Case-insensitive match over name, email, phone and skills. */
export function advisorMatches(advisor: Advisor, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    advisor.full_name.toLowerCase().includes(q) ||
    (advisor.email ?? "").toLowerCase().includes(q) ||
    (advisor.phone_e164 ?? "").toLowerCase().includes(q) ||
    (advisor.sip_uri ?? "").toLowerCase().includes(q) ||
    advisor.skills.some((s) => s.toLowerCase().includes(q))
  );
}

/**
 * Comma-separated input -> normalised tag list. Lower-cased: _skills() in
 * advisors.py lower-cases before matching, so casing is never behavioural.
 */
export function parseSkills(input: string): string[] {
  const seen = new Set<string>();
  for (const raw of input.split(",")) {
    const tag = raw.trim().toLowerCase();
    if (tag) seen.add(tag);
  }
  return [...seen];
}
