import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/**
 * The callback queue.
 *
 * Contract notes that are easy to get wrong and are enforced here:
 *  - `status: ""` is the ONLY way to list every status (business_api/callbacks.py:list_callbacks
 *    guards the filter with `if status:`). It must be sent explicitly; omitting it defaults to
 *    "pending" server-side.
 *  - `overdue_only` is orthogonal to `status`, so only the combinations produced by the UI's five
 *    scopes are ever emitted.
 *  - complete/cancel take a REQUIRED body. Omitting it is a 422.
 */

export type Callback = {
  id: string;
  status: string;
  scheduled_time: string | null;
  preferred_window: string | null;
  reason: string | null;
  priority_level: number;
  attempts: number;
  outcome_note: string | null;
  completed_at: string | null;
  overdue: boolean;
  customer_id: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  assigned_advisor_id: string | null;
  assigned_advisor_name: string | null;
  session_id: string | null;
};

export type CallbackStats = {
  pending: number;
  overdue: number;
  completed: number;
};

// "" is meaningful (all statuses) — do not coerce it away.
const ListInput = z.object({
  status: z.enum(["pending", "completed", "cancelled", ""]),
  overdueOnly: z.boolean(),
  limit: z.number().int().min(1).max(1000),
});

const OutcomeInput = z.object({
  callbackId: z.string().min(1),
  note: z.string().max(500),
  reached: z.boolean(),
});

const CancelInput = z.object({
  callbackId: z.string().min(1),
  note: z.string().max(500),
});

export const listCallbacks = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    const result = await businessApi<{ callbacks: Callback[] }>("/api/v1/callbacks", {
      method: "GET",
      query: {
        status: data.status,
        overdue_only: data.overdueOnly,
        limit: data.limit,
      },
      role: context.session.role,
    });
    return result.callbacks ?? [];
  });

export const getCallbackStats = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) =>
    businessApi<CallbackStats>("/api/v1/callbacks/stats", {
      method: "GET",
      role: context.session.role,
    }),
  );

/**
 * reached=true  -> status becomes 'completed', completed_at is stamped.
 * reached=false -> status stays 'pending', assigned_advisor_id is cleared, attempts is NOT
 *                  incremented (only claim_next does that).
 * An empty note leaves any existing note in place; it cannot be cleared.
 */
export const completeCallback = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => OutcomeInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Callback>(`/api/v1/callbacks/${data.callbackId}/complete`, {
      method: "POST",
      body: { note: data.note, reached: data.reached },
      role: context.session.role,
    }),
  );

/** cancel_callback reads only `note`; `reached` is deliberately not sent. */
export const cancelCallback = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => CancelInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Callback>(`/api/v1/callbacks/${data.callbackId}/cancel`, {
      method: "POST",
      body: { note: data.note },
      role: context.session.role,
    }),
  );
