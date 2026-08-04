import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what SupervisionRepository.decision_ledger() serialises ---------- */

export type DecisionAction = {
  id: string;
  action_type: string;
  target_domain: string;
  status: "pending" | "succeeded" | "failed" | "retrying";
  attempt_count: number;
  idempotency_key: string;
  reference: string | null;
  error_message: string | null;
  parameters: Record<string, string | number | boolean | null>;
  created_at: string | null;
  updated_at: string | null;
};

export type Decision = {
  id: string;
  session_id: string;
  customer_id: string | null;
  action: string;
  direction: "inbound" | "outbound";
  verdict: "AUTHORIZED" | "REFUSED" | "ESCALATE";
  rule_id: string;
  justification: string;
  inputs_snapshot: Record<string, string | number | boolean | null>;
  created_at: string | null;
  actions: DecisionAction[];
};

/** Verdicts are stored uppercase (CheckConstraint); never lowercase for display logic. */
export const verdictValues = z.enum(["AUTHORIZED", "REFUSED", "ESCALATE"]);
export type Verdict = z.infer<typeof verdictValues>;

/** Response is a bare envelope { decisions: [...] }, not a raw array. */
export type DecisionList = { decisions: Decision[] };

/* ---------- schemas ---------- */

const ListInput = z.object({
  /** Empty means "no verdict filter" — the empty-filter convention (C8 §3.2). */
  verdict: verdictValues.optional(),
});

/* ---------- server functions ---------- */

export const listDecisions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<DecisionList>("/api/v1/decisions", {
      method: "GET",
      query: {
        limit: 100,
        ...(data.verdict ? { verdict: data.verdict } : {}),
      },
      role: context.session.role,
    });
  });

/* G10 — reuse the already-exposed verdict_distribution from telemetry/timeline. */
export type VerdictDistribution = {
  authorized: number;
  refused: number;
  escalated: number;
};

export const getVerdictDistribution = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) => {
    return businessApi<{
      verdict_distribution: VerdictDistribution;
    }>("/api/v1/telemetry/timeline", {
      method: "GET",
      role: context.session.role,
    });
  });
