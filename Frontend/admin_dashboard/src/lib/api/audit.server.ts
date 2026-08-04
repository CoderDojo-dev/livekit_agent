import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

/* ---------- wire types: exactly what the three backend endpoints serialise ---------- */

export type AuditVerification = { intact: boolean; entries: number };

export type IntegrityReport = {
  ok: boolean;
  orphans: Record<string, number>;
  audit_chain_intact: boolean;
  audit_entries: number;
};

export type AuditEntry = {
  seq: number;
  event_type: string;
  entity_reference: string | null;
  session_id: string | null;
  entry_hash: string;
  previous_hash: string;
  created_at: string;
  payload: Record<string, string | number | boolean | null>;
};

export type AuditEntryPage = {
  entries: AuditEntry[];
  has_more: boolean;
  next_before_seq: number | null;
};

export type RetentionReport = {
  cutoff: string;
  sessions_matched: number;
  turns_anonymized: number;
  dry_run: boolean;
};

/* ---------- server functions ---------- */

/** Whole-chain SHA-256 recomputation. Expensive and unbounded - never auto-run. See F3. */
export const verifyAuditChain = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .handler(async ({ context }) =>
    businessApi<AuditVerification>("/api/v1/audit/verify", { role: context.session.role }),
  );

/** Also recomputes the whole chain internally, plus four COUNT(*)s. See F5. */
export const runIntegrityReport = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .handler(async ({ context }) =>
    businessApi<IntegrityReport>("/api/v1/jobs/integrity", { role: context.session.role }),
  );

export const listAuditEntries = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { beforeSeq?: number; eventType?: string };
    return {
      beforeSeq: typeof input.beforeSeq === "number" ? input.beforeSeq : undefined,
      eventType: input.eventType?.trim() || undefined,
    };
  })
  .handler(async ({ data, context }) =>
    businessApi<AuditEntryPage>("/api/v1/audit/entries", {
      query: {
        limit: 50,
        ...(data.beforeSeq === undefined ? {} : { before_seq: data.beforeSeq }),
        ...(data.eventType === undefined ? {} : { event_type: data.eventType }),
      },
      role: context.session.role,
    }),
  );

/**
 * Retention. `retention_days` and `dry_run` are QUERY parameters - the backend route has no
 * body model, so a JSON body is silently ignored and the defaults (90, dry_run=true) apply. F8.
 */
export const runRetention = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { retentionDays?: unknown; dryRun?: unknown };
    const days = Number(input.retentionDays);
    if (!Number.isInteger(days) || days < 30 || days > 3650) {
      throw new Error("Retention window must be a whole number between 30 and 3650 days.");
    }
    return { retentionDays: days, dryRun: input.dryRun !== false };
  })
  .handler(async ({ data, context }) =>
    businessApi<RetentionReport>("/api/v1/jobs/retention", {
      method: "POST",
      query: { retention_days: data.retentionDays, dry_run: data.dryRun },
      role: context.session.role,
    }),
  );
