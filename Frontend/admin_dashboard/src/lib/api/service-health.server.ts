import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { requireRole } from "@/lib/api/middleware";

export type ServiceHealthStatus = "reachable" | "degraded" | "unavailable" | "unknown";
export type ServiceHealthProbeKind = "liveness" | "readiness" | "none";
export type ServiceHealthEntry = {
  id: string;
  name: string;
  domain: string;
  monitoring_configured: boolean;
  probe_kind: ServiceHealthProbeKind;
  required: boolean;
  status: ServiceHealthStatus;
  reason: string;
  latency_ms: number | null;
};
export type ServiceHealthReport = {
  schema_version: 1;
  overall: ServiceHealthStatus;
  checked_at: string;
  cache_ttl_ms: number;
  probe_timeout_ms: number;
  business_api_liveness: { status: "reachable"; reason: "request_served" };
  services: ServiceHealthEntry[];
};

/** Server-only BFF adapter: the browser never receives internal addresses or credentials. */
export const getServiceHealth = createServerFn({ method: "GET" })
  .middleware([requireRole("administrateur")])
  .handler(async ({ context }) =>
    businessApi<ServiceHealthReport>("/api/v1/system/health", { role: context.session.role }),
  );
