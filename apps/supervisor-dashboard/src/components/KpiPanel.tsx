import { useEffect, useState } from "react";
import { api } from "../api";
import type { Kpis } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function KpiPanel() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.kpis().then(setKpis).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">Could not load KPIs: {error}</p>;
  if (!kpis) return <p className="muted">Loading KPIs…</p>;

  const cards = [
    { label: "Containment rate", value: pct(kpis.containment_rate), hint: "resolved / total" },
    { label: "Escalation rate", value: pct(kpis.escalation_rate), hint: "escalated / total" },
    { label: "Avg. peak frustration", value: kpis.avg_frustration.toFixed(2), hint: "0 = calm" },
    { label: "Total sessions", value: String(kpis.total_sessions), hint: "" },
    { label: "Resolved", value: String(kpis.resolved), hint: "" },
    { label: "Escalated", value: String(kpis.escalated), hint: "" },
  ];

  return (
    <div className="cards">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <div className="card-value">{c.value}</div>
          <div className="card-label">{c.label}</div>
          {c.hint && <div className="card-hint">{c.hint}</div>}
        </div>
      ))}
    </div>
  );
}