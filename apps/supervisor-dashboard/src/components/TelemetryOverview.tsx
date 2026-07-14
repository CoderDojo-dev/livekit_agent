import { Button, Column, Grid, SkeletonPlaceholder, Tile } from "@carbon/react";
import { ArrowRight } from "@carbon/icons-react";
import { DonutChart, LineChart } from "@carbon/charts-react";
import { ChartTheme, ScaleTypes } from "@carbon/charts";
import type { DonutChartOptions, LineChartOptions } from "@carbon/charts";
import { api } from "../api";
import { usePoll } from "../refresh";
import { ErrorBanner, PageHeader, pct } from "./shared";
export function TelemetryOverview({
  onInspectSession,
}: {
  onInspectSession: (id: string) => void;
}) {
  const kpis = usePoll(api.kpis);
  const timeline = usePoll(api.telemetryTimeline);
  const overview = usePoll(api.systemOverview);
  const error = kpis.error ?? timeline.error ?? overview.error;
  if (error) {
    return (
      <>
        <PageHeader title="Telemetry overview" />
        <ErrorBanner title="Failed to synchronise telemetry" error={error} />
      </>
    );
  }
  if (!kpis.data || !timeline.data || !overview.data) {
    return (
      <>
        <PageHeader
          title="Telemetry overview"
          subtitle="Real-time conversational KPIs, frustration trends and policy gate verdicts"
        />
        <Grid fullWidth className="stack-grid">
          {[0, 1, 2, 3].map((i) => (
            <Column key={i} sm={4} md={4} lg={4}>
              <SkeletonPlaceholder className="kpi-skeleton" />
            </Column>
          ))}
        </Grid>
        <SkeletonPlaceholder className="chart-skeleton" />
      </>
    );
  }
  const k = kpis.data;
  const t = timeline.data;
  const o = overview.data;
  const lineData = t.timeline.flatMap((p) => [
    { group: "Session duration (s)", key: p.timestamp, value: p.duration },
    { group: "Frustration index", key: p.timestamp, value: p.frustration },
  ]);
  const lineOptions: LineChartOptions = {
    axes: {
      bottom: { title: "Session start", mapsTo: "key", scaleType: ScaleTypes.LABELS },
      left: { title: "Duration (s)", mapsTo: "value" },
      right: {
        title: "Frustration (0–1)",
        mapsTo: "value",
        correspondingDatasets: ["Frustration index"],
        domain: [0, 1],
      },
    },
    curve: "curveMonotoneX",
    height: "320px",
    theme: ChartTheme.G100,
    color: {
      scale: {
        "Session duration (s)": "#4589ff",
        "Frustration index": "#ff7eb6",
      },
    },
  };
  const donutData = [
    { group: "Authorized", value: t.verdict_distribution.authorized },
    { group: "Refused", value: t.verdict_distribution.refused },
    { group: "Escalate", value: t.verdict_distribution.escalated },
  ];
  const donutOptions: DonutChartOptions = {
    donut: { center: { label: "verdicts" } },
    height: "280px",
    theme: ChartTheme.G100,
    color: {
      scale: { Authorized: "#42be65", Refused: "#fa4d56", Escalate: "#f1c21b" },
    },
  };
  return (
    <>
      <PageHeader
        title="Telemetry overview"
        subtitle="Real-time conversational KPIs, frustration trends and policy gate verdicts, computed over call_sessions, sentiment_samples and policy_verdicts"
      />
      <Grid fullWidth className="stack-grid dashboard-section">
        <Column sm={4} md={4} lg={4}>
          <Tile className="kpi-tile kpi-tile--success">
            <div>
              <p className="kpi-tile__label">Containment rate</p>
              <p className="kpi-tile__value">{pct(k.containment_rate)}</p>
            </div>
            <p className="kpi-tile__hint">{k.resolved} sessions resolved autonomously</p>
          </Tile>
        </Column>
        <Column sm={4} md={4} lg={4}>
          <Tile className="kpi-tile kpi-tile--danger">
            <div>
              <p className="kpi-tile__label">Escalation rate</p>
              <p className="kpi-tile__value">{pct(k.escalation_rate)}</p>
            </div>
            <p className="kpi-tile__hint">{k.escalated} sessions handed to human queue</p>
          </Tile>
        </Column>
        <Column sm={4} md={4} lg={4}>
          <Tile className="kpi-tile kpi-tile--warning">
            <div>
              <p className="kpi-tile__label">Avg. peak frustration</p>
              <p className="kpi-tile__value">{k.avg_frustration.toFixed(2)}</p>
            </div>
            <p className="kpi-tile__hint">Escalation trigger threshold: 0.75</p>
          </Tile>
        </Column>
        <Column sm={4} md={4} lg={4}>
          <Tile className="kpi-tile kpi-tile--info">
            <div>
              <p className="kpi-tile__label">Voice sessions</p>
              <p className="kpi-tile__value">{k.total_sessions}</p>
            </div>
            <p className="kpi-tile__hint">LiveKit WebRTC call records</p>
          </Tile>
        </Column>
      </Grid>
      <Grid fullWidth className="stack-grid dashboard-section">
        <Column sm={4} md={8} lg={11}>
          <Tile className="chart-tile">
            <p className="chart-tile__title">
              Session duration vs. peak frustration — last {t.timeline.length} sessions
            </p>
            <LineChart data={lineData} options={lineOptions} />
          </Tile>
        </Column>
        <Column sm={4} md={8} lg={5}>
          <Tile className="chart-tile">
            <p className="chart-tile__title">Policy gate verdict distribution</p>
            <DonutChart data={donutData} options={donutOptions} />
          </Tile>
        </Column>
      </Grid>
      <Grid fullWidth className="stack-grid">
        <Column sm={4} md={4} lg={8}>
          <Tile className="chart-tile">
            <p className="chart-tile__title">Storage & ledger volumes (PostgreSQL)</p>
            <div className="stat-list">
              <div className="stat-list__row">
                <span>Customer profiles</span>
                <span className="stat-list__value">{o.metrics.total_customers}</span>
              </div>
              <div className="stat-list__row">
                <span>Conversation turns</span>
                <span className="stat-list__value">{o.metrics.total_turns}</span>
              </div>
              <div className="stat-list__row">
                <span>Audit ledger records</span>
                <span className="stat-list__value">{o.metrics.total_audit_entries}</span>
              </div>
              <div className="stat-list__row">
                <span>Idempotent actions</span>
                <span className="stat-list__value">{o.metrics.total_actions}</span>
              </div>
              <div className="stat-list__row">
                <span>Escalation cases</span>
                <span className="stat-list__value">{o.metrics.total_escalations}</span>
              </div>
            </div>
          </Tile>
        </Column>
        <Column sm={4} md={4} lg={8}>
          <Tile className="chart-tile">
            <p className="chart-tile__title">Operational shortcuts</p>
            <p className="muted" style={{ fontSize: "0.8125rem", marginBottom: "1rem" }}>
              Jump into the Session Inspector to review a PII-masked transcript, sentiment
              trajectory and policy verdicts for any call session UUID.
            </p>
            <Button kind="tertiary" renderIcon={ArrowRight} onClick={() => onInspectSession("")}>
              Open Session Inspector
            </Button>
          </Tile>
        </Column>
      </Grid>
    </>
  );
}
