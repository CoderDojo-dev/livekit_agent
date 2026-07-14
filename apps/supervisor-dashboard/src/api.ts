import type {
  Action,
  AuditVerifyResponse,
  BusinessRule,
  Customer360Data,
  Escalation,
  IntegrityReport,
  Kpis,
  SessionDetail,
  SystemOverview,
  TelemetryTimeline,
  Verdict,
} from "./types";

const BASE = import.meta.env.VITE_BUSINESS_API_URL ?? "http://localhost:8108";
const ROLE = import.meta.env.VITE_API_ROLE ?? "administrateur";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "X-Role": ROLE } });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  kpis: () => get<Kpis>("/api/v1/kpis"),
  escalations: (status = "open") =>
    get<{ escalations: Escalation[] }>(`/api/v1/escalations?status=${encodeURIComponent(status)}`),
  session: (id: string) => get<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(id)}`),
  verdicts: (id: string) =>
    get<{ verdicts: Verdict[] }>(`/api/v1/policy/verdicts?session_id=${encodeURIComponent(id)}`),
  actions: (status = "failed") =>
    get<{ actions: Action[] }>(`/api/v1/actions?status=${encodeURIComponent(status)}`),
  businessRules: () =>
    get<{ rules: BusinessRule[] }>("/api/v1/reference/business-rules"),
  auditVerify: () => get<AuditVerifyResponse>("/api/v1/audit/verify"),
  integrityJob: () => get<IntegrityReport>("/api/v1/jobs/integrity"),
  customer360: (customerId: string) =>
    get<Customer360Data>(`/api/v1/customers/${encodeURIComponent(customerId)}/360`),
  systemOverview: () => get<SystemOverview>("/api/v1/system/overview"),
  telemetryTimeline: () => get<TelemetryTimeline>("/api/v1/telemetry/timeline"),
};
