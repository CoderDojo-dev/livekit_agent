import { useEffect, useState } from "react";
import {
  Button,
  Column,
  Grid,
  SkeletonPlaceholder,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
  Tile,
} from "@carbon/react";
import { Search } from "@carbon/icons-react";
import { LineChart } from "@carbon/charts-react";
import { ChartTheme, ScaleTypes } from "@carbon/charts";
import type { LineChartOptions } from "@carbon/charts";
import { api } from "../api";
import { usePoll } from "../refresh";
import type { SessionDetail, Verdict } from "../types";
import { ErrorBanner, PageHeader, VerdictTag } from "./shared";
export function SessionInspector({ initialId }: { initialId: string }) {
  const [id, setId] = useState(initialId);
  const [query, setQuery] = useState(initialId);
  useEffect(() => {
    setId(initialId);
    setQuery(initialId);
  }, [initialId]);
  const session = usePoll<SessionDetail | null>(
    () => (id ? api.session(id) : Promise.resolve(null)),
    [id]
  );
  const verdicts = usePoll<Verdict[]>(
    () =>
      id
        ? api
            .verdicts(id)
            .then((r) => r.verdicts)
            .catch(() => [])
        : Promise.resolve([]),
    [id]
  );
  const s = session.data;
  const samples = s?.sentiment ?? [];
  const sentimentData = samples.map((sample) => ({
    group: "Frustration",
    key: `Turn ${sample.index}`,
    value: sample.score,
  }));
  const sentimentOptions: LineChartOptions = {
    axes: {
      bottom: { mapsTo: "key", scaleType: ScaleTypes.LABELS, title: "Conversation turn" },
      left: {
        mapsTo: "value",
        title: "Frustration score",
        domain: [0, 1],
        thresholds: [{ value: 0.75, label: "Escalation threshold", fillColor: "#fa4d56" }],
      },
    },
    curve: "curveMonotoneX",
    height: "280px",
    theme: ChartTheme.G100,
    color: { scale: { Frustration: "#ff7eb6" } },
    points: { radius: 4 },
  };
  return (
    <>
      <PageHeader
        title="Session inspector"
        subtitle="Turn-by-turn PII-masked transcript, sentiment trajectory and deterministic policy verdicts for one call session"
      />
      <div className="inline-form">
        <TextInput
          id="session-uuid"
          labelText="Session UUID"
          placeholder="e.g. from the escalation queue or action ledger"
          className="mono"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && setId(query.trim())}
        />
        <Button renderIcon={Search} onClick={() => setId(query.trim())}>
          Inspect
        </Button>
      </div>
      {session.error && <ErrorBanner title="Session inspection failed" error={session.error} />}
      {!id && (
        <div className="table-empty">
          Enter a call session UUID above, or open one from the Escalation Queue / Action Ledger.
        </div>
      )}
      {id && session.loading && !s && (
        <Grid fullWidth className="stack-grid">
          {[0, 1, 2].map((i) => (
            <Column key={i} sm={4} md={4} lg={5}>
              <SkeletonPlaceholder className="kpi-skeleton" />
            </Column>
          ))}
        </Grid>
      )}
      {s && (
        <>
          <Grid fullWidth className="stack-grid dashboard-section">
            <Column sm={4} md={4} lg={5}>
              <Tile
                className={`kpi-tile ${
                  s.disposition === "resolved"
                    ? "kpi-tile--success"
                    : s.disposition === "escalated"
                      ? "kpi-tile--warning"
                      : "kpi-tile--info"
                }`}
              >
                <div>
                  <p className="kpi-tile__label">Final disposition</p>
                  <p className="kpi-tile__value" style={{ fontSize: "1.5rem" }}>
                    {(s.disposition ?? "in progress").toUpperCase()}
                  </p>
                </div>
                <p className="kpi-tile__hint">Outcome recorded in call_sessions</p>
              </Tile>
            </Column>
            <Column sm={4} md={4} lg={5}>
              <Tile className="kpi-tile kpi-tile--info">
                <div>
                  <p className="kpi-tile__label">Duration</p>
                  <p className="kpi-tile__value">
                    {s.duration_seconds ?? "—"}
                    <span style={{ fontSize: "1rem" }} className="muted">
                      {" "}
                      s
                    </span>
                  </p>
                </div>
                <p className="kpi-tile__hint">Total active WebRTC stream time</p>
              </Tile>
            </Column>
            <Column sm={4} md={4} lg={6}>
              <Tile
                className={`kpi-tile ${
                  s.max_frustration >= 0.75 ? "kpi-tile--danger" : "kpi-tile--success"
                }`}
              >
                <div>
                  <p className="kpi-tile__label">Peak frustration</p>
                  <p className="kpi-tile__value">{s.max_frustration.toFixed(2)}</p>
                </div>
                <p className="kpi-tile__hint">
                  Highest sentiment index over {s.sentiment.length} turn samples
                </p>
              </Tile>
            </Column>
          </Grid>
          {samples.length > 0 && (
            <Tile className="chart-tile dashboard-section">
              <p className="chart-tile__title">Frustration trajectory — sentiment per turn</p>
              <LineChart data={sentimentData} options={sentimentOptions} />
            </Tile>
          )}
          <div className="dashboard-section">
            <TableContainer
              title="Policy gate verdicts"
              description="Deterministic PolicyService checkpoint decisions recorded for this session"
            >
              <Table size="lg">
                <TableHead>
                  <TableRow>
                    <TableHeader>Verdict</TableHeader>
                    <TableHeader>Requested action</TableHeader>
                    <TableHeader>Rule ID</TableHeader>
                    <TableHeader>Justification</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(verdicts.data ?? []).map((v) => (
                    <TableRow key={v.id}>
                      <TableCell>
                        <VerdictTag verdict={v.verdict} />
                      </TableCell>
                      <TableCell>
                        <strong className="mono">{v.action}</strong>
                      </TableCell>
                      <TableCell>
                        <span className="mono">{v.rule_id}</span>
                      </TableCell>
                      <TableCell>{v.justification}</TableCell>
                    </TableRow>
                  ))}
                  {(verdicts.data ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <span className="muted">
                          No policy verdicts required or recorded for this session.
                        </span>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </div>
          <TableContainer
            title="Conversation transcript"
            description="PII-masked, turn-by-turn record from the Turn ledger"
          >
            <div className="transcript">
              {s.turns.map((t) => (
                <div
                  key={`${t.index}-${t.speaker}`}
                  className={`transcript__turn transcript__turn--${
                    t.speaker === "caller" ? "caller" : "agent"
                  }`}
                >
                  <div className="transcript__meta">
                    Turn {t.index} ·{" "}
                    {t.speaker === "caller" ? "Caller (human)" : (t.agent ?? "AI agent")}
                  </div>
                  <div className="transcript__text">{t.text ?? "—"}</div>
                </div>
              ))}
              {s.turns.length === 0 && (
                <span className="muted">No transcript turns recorded yet.</span>
              )}
            </div>
          </TableContainer>
          <div style={{ marginTop: "0.5rem" }}>
            <Tag size="sm" type="outline" className="mono">
              {s.session_id}
            </Tag>
          </div>
        </>
      )}
    </>
  );
}
