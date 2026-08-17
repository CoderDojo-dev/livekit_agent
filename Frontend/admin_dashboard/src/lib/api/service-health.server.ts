import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type ServiceHealthStatus = "reachable" | "degraded" | "unavailable" | "unknown";
export type ServiceHealthEntry = {
  name: string;
  domain: string;
  configured: boolean;
  required: boolean;
  status: ServiceHealthStatus;
  reason: string;
  latency_ms: number | null;
};
export type ServiceHealthReport = {
  schema_version: 1;
  overall: ServiceHealthStatus;
  checked_at: string;
  timeout_ms: number;
  services: ServiceHealthEntry[];
};

/** Server-only BFF adapter: the browser never receives internal addresses or credentials. */
export const getServiceHealth = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .handler(async ({ context }) =>
    businessApi<ServiceHealthReport>("/api/v1/system/health", { role: context.session.role }),
  );
