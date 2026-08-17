import type { RequestItem } from "@/lib/api/requests.server";

/**
 * Status -> chip tone for tickets, and the "still being worked on" predicate.
 *
 * Lives in lib, not in a route file: raw status values must only appear inside
 * label maps (verify-portal.sh enforces it).
 */
export const REQUEST_TONE: Record<RequestItem["status"], "solid" | "outline" | "dashed" | "muted"> =
  {
    open: "dashed",
    in_progress: "solid",
    pending: "dashed",
    resolved: "outline",
    closed: "muted",
  };

export function isActiveRequest(status: RequestItem["status"]): boolean {
  return status === "open" || status === "in_progress" || status === "pending";
}
