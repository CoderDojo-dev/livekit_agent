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