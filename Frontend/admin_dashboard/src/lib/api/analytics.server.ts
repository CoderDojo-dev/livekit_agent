import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type KpiBundle = {
  total_sessions: number;
  resolved: number;
  escalated: number;
  containment_rate: number; // 0..1, NOT a percentage
  escalation_rate: number; // 0..1
  avg_frustration: number;
};

export type PlatformMetrics = {
  total_calls: number;
  total_turns: number;
  total_verdicts: number;
  total_actions: number;
  total_audit_entries: number;
  total_customers: number;
  total_escalations: number;
};

/** `status` is deliberately absent from this type: the backend hardcodes it. See Cookbook 9 §0. */
export type ServiceEntry = { name: string; port: number; domain: string };

export type SystemOverview = { metrics: PlatformMetrics; services: ServiceEntry[] };

export type VerdictDistribution = { authorized: number; refused: number; escalated: number };

export type TrendPoint = { day: string; current: number; previous: number };

export type AnalyticsTrend = {
  days: number;
  timezone: string;
  current: KpiBundle;
  previous: KpiBundle;
  daily: TrendPoint[];
};

export const getKpis = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) =>
    businessApi<KpiBundle>("/api/v1/kpis", { role: context.session.role }),
  );

export const getSystemOverview = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .handler(async ({ context }) => {
    const raw = await businessApi<{
      metrics: PlatformMetrics;
      services: Array<ServiceEntry & { status?: string }>;
    }>("/api/v1/system/overview", { role: context.session.role });

    // Strip `status` at the boundary so no component can render it by accident.
    return {
      metrics: raw.metrics,
      services: raw.services.map(({ name, port, domain }) => ({ name, port, domain })),
    } satisfies SystemOverview;
  });

export const getAnalyticsTrend = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((raw: unknown) => {
    const days = Number((raw as { days?: unknown })?.days ?? 7);
    return { days: [7, 14, 30].includes(days) ? days : 7 };
  })
  .handler(async ({ data, context }) =>
    businessApi<AnalyticsTrend>("/api/v1/analytics/trend", {
      method: "GET",
      query: { days: data.days },
      role: context.session.role,
    }),
  );
