import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what SupervisionRepository.escalations() serialises ---------- */

export type Escalation = {
  id: string;
  session_id: string;
  trigger: string;
  target: string;
  resolution: string | null;
  dossier: Record<string, string | number | boolean | null>;
  /** Batch 1 / C13 — added to the repository dict (additive). */
  created_at: string | null;
  /** Batch 5 — customer identity projection (case id, then session id, then null). */
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean | null;
};

/**
 * The backend treats ONLY the literal "open" as a filter; every other value returns all rows
 * (4.1). "all" is our sentinel for that branch, not a supported enum member.
 */
export const escalationScope = z.enum(["open", "all"]);
export type EscalationScope = z.infer<typeof escalationScope>;

/** Response is a bare envelope { escalations: [...] }, not a raw array. */
export type EscalationList = { escalations: Escalation[] };

const ListInput = z.object({
  scope: escalationScope.default("open"),
});

export const listEscalations = createServerFn({ method: "GET" })
  .middleware([requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<EscalationList>("/api/v1/escalations", {
      method: "GET",
      query: { status: data.scope },
      role: context.session.role,
    });
  });

export const escalationResolution = z.enum([
  "transferred",
  "queued",
  "callback_scheduled",
  "resolved",
]);
export type EscalationResolution = z.infer<typeof escalationResolution>;

const CloseInput = z.object({
  id: z.string().min(1),
  resolution: escalationResolution,
});

export const closeEscalation = createServerFn({ method: "POST" })
  .middleware([requireRole("superviseur")])
  .inputValidator((data: unknown) => CloseInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<Escalation>(`/api/v1/escalations/${data.id}/close`, {
      method: "POST",
      body: { resolution: data.resolution },
      role: context.session.role,
    });
  });
