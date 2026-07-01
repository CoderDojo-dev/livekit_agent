import type { Escalation, Kpis, SessionDetail, Verdict } from "./types";

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
};