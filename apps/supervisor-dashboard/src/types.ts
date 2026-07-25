export interface Kpis {
  total_sessions: number;
  resolved: number;
  escalated: number;
  containment_rate: number;
  escalation_rate: number;
  avg_frustration: number;
}

export interface Escalation {
  id: string;
  session_id: string;
  trigger: string;
  target: string;
  resolution: string | null;
  dossier: Record<string, unknown>;
}

export interface Verdict {
  id: string;
  action: string;
  verdict: string; // AUTHORIZED | REFUSED | ESCALATE
  rule_id: string;
  justification: string;
}

export interface Turn {
  index: number;
  speaker: string;
  agent: string | null;
  text: string | null;
}

export interface SentimentSample {
  index: number;
  score: number;
  label: string | null;
}

export interface SessionDetail {
  session_id: string;
  disposition: string | null;
  duration_seconds: number | null;
  max_frustration: number;
  turns: Turn[];
  sentiment: SentimentSample[];
}

export interface Action {
  id: string;
  action_type: string;
  status: string; // failed | succeeded | pending
  idempotency_key: string;
  reference: string | null;
}

export interface BusinessRule {
  rule_id: string;
  domain: string;
  version: number;
  active: boolean;
  description: string;
  definition?: Record<string, unknown>;
  enforced?: boolean;
  governed_by?: string[];
  source?: string;
}

export interface AuditVerifyResponse {
  intact: boolean;
  entries: number;
}

export interface IntegrityReport {
  ok: boolean;
  orphans: Record<string, unknown>;
  audit_chain_intact: boolean;
  audit_entries: number;
}

export interface ServiceProbe {
  name: string;
  port: number;
  domain: string;
  status: "online" | "offline" | "degraded";
}

export interface SystemOverview {
  metrics: {
    total_calls: number;
    total_turns: number;
    total_verdicts: number;
    total_actions: number;
    total_audit_entries: number;
    total_customers: number;
    total_escalations: number;
  };
  services: ServiceProbe[];
}

export interface TelemetryPoint {
  timestamp: string;
  duration: number;
  frustration: number;
  disposition: string;
}

export interface TelemetryTimeline {
  timeline: TelemetryPoint[];
  verdict_distribution: {
    authorized: number;
    refused: number;
    escalated: number;
  };
}

export interface CustomerSubscription {
  subscription_id: string;
  msisdn: string;
  plan: string;
  status: string;
}

export interface CustomerInvoice {
  invoice: string;
  amount: number;
  status: string;
}

export interface CustomerTicket {
  glpi_id: string;
  status: string;
  subject: string;
}

export interface Customer360Data {
  customer_id: string;
  name: string;
  vip: boolean;
  preferred_language: string;
  subscriptions: CustomerSubscription[];
  open_invoices: CustomerInvoice[];
  tickets: CustomerTicket[];
}

export interface Callback {
  id: string;
  status: "pending" | "completed" | "cancelled";
  scheduled_time: string | null;
  /** The caller's own words, e.g. "demain matin" - kept verbatim. */
  preferred_window: string | null;
  reason: string | null;
  priority_level: number;
  attempts: number;
  outcome_note: string | null;
  completed_at: string | null;
  overdue: boolean;
  customer_id: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  assigned_advisor_id: string | null;
  assigned_advisor_name: string | null;
  session_id: string | null;
}

export interface CallbackStats {
  pending: number;
  overdue: number;
  completed: number;
}
