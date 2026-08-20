import { createServerFn } from "@tanstack/react-start";

import { authedMiddleware } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";
import { hasRank } from "@/lib/api/session";

/**
 * Counts for the sidebar badges.
 *
 * WHY THIS EXISTS AS ITS OWN SERVER FUNCTION
 * The three numbers come from three different upstreams. Fetching them from the sidebar with
 * three separate client queries would mean three round trips on every page, three loading states
 * in a 236px rail, and a badge row that fills in raggedly. One server function fans out
 * server-side (where the calls are local to business-api) and returns a single object.
 *
 * DESIGN RULES, all deliberate:
 *
 *  1. `authedMiddleware`, NOT `requireRole`. The badges must degrade for a `conseiller`, never
 *     403 the whole rail. Role is checked per-source below and an ineligible source returns null.
 *
 *  2. `Promise.allSettled`, never `Promise.all`. If the callback service is down, the tickets
 *     badge must still render. A rejected source becomes null.
 *
 *  3. `null` means "not known", and is rendered as NO BADGE — never as 0. A zero badge is a
 *     claim ("nothing is waiting"); an absent badge is an admission ("we could not ask"). The
 *     product's existing honesty discipline (see the `no delta exists` comments) requires the
 *     distinction.
 */

export type NavCounts = {
  /** Open handoffs awaiting a human. null = not permitted or not reachable. */
  escalations: number | null;
  /** Pending callbacks in the queue. */
  callbacks: number | null;
  /** Tickets in the `open` state — not the mirror's total. */
  tickets: number | null;
};

const EMPTY: NavCounts = { escalations: null, callbacks: null, tickets: null };

/** Narrows an allSettled outcome to its value, mapping any rejection to null. */
function settled<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === "fulfilled" ? result.value : null;
}

export const getNavCounts = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async ({ context }): Promise<NavCounts> => {
    // Every source below is gated at `superviseur` upstream. Asking as a conseiller would spend
    // three round trips to collect three 403s.
    if (!hasRank(context.session, "superviseur")) return EMPTY;

    const [escalations, callbacks, tickets] = await Promise.allSettled([
      businessApi<{ escalations: unknown[] }>("/api/v1/escalations", {
        method: "GET",
        query: { status: "open" },
        role: context.session.role,
      }),
      businessApi<{ pending: number; overdue: number; completed: number }>(
        "/api/v1/callbacks/stats",
        { method: "GET", role: context.session.role },
      ),
      // limit=1 because only the `counts` envelope is wanted; the row itself is discarded.
      businessApi<{ total: number; counts: Record<string, number> }>("/api/v1/tickets", {
        method: "GET",
        query: { limit: 1, offset: 0 },
        role: context.session.role,
      }),
    ]);

    const escalationList = settled(escalations);
    const callbackStats = settled(callbacks);
    const ticketIndex = settled(tickets);

    return {
      escalations: Array.isArray(escalationList?.escalations)
        ? escalationList.escalations.length
        : null,
      callbacks: typeof callbackStats?.pending === "number" ? callbackStats.pending : null,
      // `open` specifically: a badge next to "Tickets" that counted closed ones would be noise.
      // Bracket access because `counts` is an index signature (noPropertyAccessFromIndexSignature).
      tickets:
        typeof ticketIndex?.counts?.["open"] === "number" ? ticketIndex.counts["open"] : null,
    };
  });
