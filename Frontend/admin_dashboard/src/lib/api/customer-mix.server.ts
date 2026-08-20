import { createServerFn } from "@tanstack/react-start";

import { authedMiddleware } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/**
 * Customer status distribution.
 *
 * WHY THIS EXISTS
 * The customers list returns rows plus a `total` for whatever filter was applied — it carries no
 * per-status breakdown. So the only honest way to show a distribution is to ask for each status
 * and read the totals back. Each call requests `limit=1`: the row is discarded, only the envelope
 * count is wanted, so the payload is negligible.
 *
 * Fanned out server-side (one round trip from the browser, three local ones inside the cluster)
 * for the same reason as getNavCounts: three client queries would mean three loading states in
 * one card and a distribution that fills in raggedly.
 *
 * `Promise.allSettled` and a `null` for any status we could not read — never a zero. A zero here
 * would draw an empty segment on the bar and assert "there are none", which is a different claim
 * from "we could not ask".
 */

export type CustomerMix = {
  active: number | null;
  suspended: number | null;
  closed: number | null;
};

const STATUSES = ["active", "suspended", "closed"] as const;

export const getCustomerMix = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async ({ context }): Promise<CustomerMix> => {
    const results = await Promise.allSettled(
      STATUSES.map((status) =>
        businessApi<{ total: number }>("/api/v1/customers", {
          method: "GET",
          query: { status, limit: 1, offset: 0 },
          role: context.session.role,
        }),
      ),
    );

    const read = (index: number): number | null => {
      const result = results[index];
      if (result === undefined || result.status !== "fulfilled") return null;
      return typeof result.value.total === "number" ? result.value.total : null;
    };

    return { active: read(0), suspended: read(1), closed: read(2) };
  });
