import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what policy_view.overlay() serialises ---------- */

export type PolicyRule = {
  rule_id: string;
  domain: string;
  version: number;
  active: boolean;
  description: string | null;
  definition: Record<string, number | string | boolean>;
  enforced: boolean;
  /** present only when enforced */
  governed_by?: string[];
  /** present only when enforced */
  source?: string;
};

/** Read-only registry. No query parameters at all — the empty-filter convention does not apply. */
export const listPolicyRules = createServerFn({ method: "GET" })
  .middleware([requireRole("administrateur")])
  .handler(async ({ context }) => {
    return businessApi<{ rules: PolicyRule[] }>("/api/v1/reference/business-rules", {
      method: "GET",
      role: context.session.role,
    });
  });

/* ---------------------------------------------------------------------------------------------
 * Governance writes
 *
 * WHAT IS AND IS NOT WRITABLE, and why it is safe.
 *
 * `reference.business_rules` is a GOVERNANCE RECORD. Its only readers are this console and the
 * seed script — policy-service, decision-service and agent-worker never query it; they read
 * POLICY_* environment variables. Editing a row here therefore cannot change what the agent
 * enforces, which is precisely why these operations are offered at all.
 *
 * Thresholds are absent from every payload below. They are overlaid onto each governed rule at
 * read time from the live env, so there is nothing numeric here to write — and accepting one
 * would let the registry advertise a limit the engine is not applying.
 *
 * business-api additionally refuses to deactivate or delete a GOVERNED rule; those calls surface
 * here as a 409 with the reason, which the UI shows verbatim rather than guessing.
 * ------------------------------------------------------------------------------------------- */

const RuleIdInput = z.object({ ruleId: z.string().min(1).max(80) });

const CreateRuleInput = z.object({
  ruleId: z.string().trim().min(1).max(80),
  domain: z.string().trim().max(40).default("general"),
  description: z.string().trim().max(4000).optional(),
});

const UpdateRuleInput = z.object({
  ruleId: z.string().min(1).max(80),
  description: z.string().max(4000).optional(),
  active: z.boolean().optional(),
});

export const createPolicyRule = createServerFn({ method: "POST" })
  .middleware([requireRole("administrateur")])
  .inputValidator((data: unknown) => CreateRuleInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<PolicyRule>("/api/v1/reference/business-rules", {
      method: "POST",
      body: {
        rule_id: data.ruleId,
        domain: data.domain,
        ...(data.description === undefined ? {} : { description: data.description }),
      },
      role: context.session.role,
    }),
  );

export const updatePolicyRule = createServerFn({ method: "POST" })
  .middleware([requireRole("administrateur")])
  .inputValidator((data: unknown) => UpdateRuleInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<PolicyRule>(`/api/v1/reference/business-rules/${encodeURIComponent(data.ruleId)}`, {
      method: "PATCH",
      body: {
        ...(data.description === undefined ? {} : { description: data.description }),
        ...(data.active === undefined ? {} : { active: data.active }),
      },
      role: context.session.role,
    }),
  );

export const deletePolicyRule = createServerFn({ method: "POST" })
  .middleware([requireRole("administrateur")])
  .inputValidator((data: unknown) => RuleIdInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<void>(`/api/v1/reference/business-rules/${encodeURIComponent(data.ruleId)}`, {
      method: "DELETE",
      role: context.session.role,
    }),
  );
