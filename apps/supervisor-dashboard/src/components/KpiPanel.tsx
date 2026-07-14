import { Column, Grid, SkeletonPlaceholder, Tile } from "@carbon/react";
import { api } from "../api";
import { usePoll } from "../refresh";
import { ErrorBanner, PageHeader, pct } from "./shared";
export function KpiPanel() {
  const { data, error, loading } = usePoll(api.kpis);
  if (error) {
    return (
      <>
        <PageHeader title="Performance KPIs" />
        <ErrorBanner title="Could not load KPIs" error={error} />
      </>
    );
  }
  const cards = data
    ? [
        {
          label: "Autonomous containment rate",
          value: pct(data.containment_rate),
          hint: "Resolved without human handoff",
          tone: "kpi-tile--success",
        },
        {
          label: "Human escalation rate",
          value: pct(data.escalation_rate),
          hint: "Transferred to supervisor queue",
          tone: "kpi-tile--danger",
        },
        {
          label: "Avg. peak frustration index",
          value: data.avg_frustration.toFixed(2),
          hint: "0.00 = calm · 1.00 = severe",
          tone: "kpi-tile--warning",
        },
        {
          label: "Total voice sessions",
          value: String(data.total_sessions),
          hint: "LiveKit WebRTC + phone records",
          tone: "kpi-tile--info",
        },
        {
          label: "Resolved sessions",
          value: String(data.resolved),
          hint: "Completed by AI personas",
          tone: "kpi-tile--success",
        },
        {
          label: "Escalated sessions",
          value: String(data.escalated),
          hint: "Active cases in escalation_cases",
          tone: "kpi-tile--danger",
        },
      ]
    : [];
  return (
    <>
      <PageHeader
        title="Performance KPIs"
        subtitle="Live containment metrics computed directly over call_sessions and sentiment_samples"
      />
      <Grid fullWidth className="stack-grid">
        {loading && !data
          ? [0, 1, 2, 3, 4, 5].map((i) => (
              <Column key={i} sm={4} md={4} lg={4}>
                <SkeletonPlaceholder className="kpi-skeleton" />
              </Column>
            ))
          : cards.map((c) => (
              <Column key={c.label} sm={4} md={4} lg={4}>
                <Tile className={`kpi-tile ${c.tone}`}>
                  <div>
                    <p className="kpi-tile__label">{c.label}</p>
                    <p className="kpi-tile__value">{c.value}</p>
                  </div>
                  <p className="kpi-tile__hint">{c.hint}</p>
                </Tile>
              </Column>
            ))}
      </Grid>
    </>
  );
}
