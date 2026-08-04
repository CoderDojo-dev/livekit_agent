import { createServerFn } from "@tanstack/react-start";
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
