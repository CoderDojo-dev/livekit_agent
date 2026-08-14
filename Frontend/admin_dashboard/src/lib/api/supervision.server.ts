import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what SupervisionRepository serialises ----------
 * These two projections are NARROW and are NOT the decision_ledger shape:
 *   verdicts() -> id, action, verdict, rule_id, justification            (5 keys, created_at ASC)
 *   actions()  -> id, action_type, status, idempotency_key, reference    (5 keys, created_at DESC)
 * Do not add created_at / attempt_count / error_message / parameters: the backend does not
 * send them on these routes, and decision_ledger's docstring states these projections keep
 * their exact shape for their existing consumers.
 */

export type SessionVerdict = {
  id: string;
  action: string;
  verdict: string;
  rule_id: string;
  justification: string;
};

export type SessionVerdictList = { verdicts: SessionVerdict[] };

/** execution.action_ledger status vocabulary — same union as decision-view's internal type. */
export type LedgerActionStatus = "pending" | "succeeded" | "failed" | "retrying";

export type LedgerAction = {
  id: string;
  action_type: string;
  status: LedgerActionStatus;
  idempotency_key: string;
  reference: string | null;
};

export type LedgerActionList = { actions: LedgerAction[] };

/* ---------- schemas ---------- */

const VerdictInput = z.object({ sessionId: z.string().uuid() });

/** Backend defaults to "failed" when absent. There is no "all" branch server-side. */
const ActionInput = z.object({
  status: z.enum(["failed", "retrying", "pending", "succeeded"]).default("failed"),
});

/* ---------- server functions ---------- */

/** GET /api/v1/policy/verdicts — session_id is a required QUERY param, not a path segment. */
export const listSessionVerdicts = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => VerdictInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<SessionVerdictList>("/api/v1/policy/verdicts", {
      method: "GET",
      query: { session_id: data.sessionId },
      role: context.session.role,
    }),
  );

/** GET /api/v1/actions — whole-ledger scan for one status, newest first. */
export const listLedgerActions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ActionInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<LedgerActionList>("/api/v1/actions", {
      method: "GET",
      query: { status: data.status },
      role: context.session.role,
    }),
  );
