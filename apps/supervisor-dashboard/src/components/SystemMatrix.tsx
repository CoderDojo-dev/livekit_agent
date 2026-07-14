import { Column, Grid, SkeletonPlaceholder, Tile } from "@carbon/react";
import { api } from "../api";
import { usePoll } from "../refresh";
import { ErrorBanner, PageHeader, StatusTag } from "./shared";
export function SystemMatrix() {
  const { data, error, loading } = usePoll(api.systemOverview);
  if (error) {
    return (
      <>
        <PageHeader title="System matrix" />
        <ErrorBanner title="Could not probe system health" error={error} />
      </>
    );
  }
  if (loading && !data) {
    return (
      <>
        <PageHeader
          title="System matrix"
          subtitle="Health-probe status and port mapping across the self-hosted telecom stack"
        />
        <Grid fullWidth className="stack-grid">
          {Array.from({ length: 6 }, (_, i) => (
            <Column key={i} sm={4} md={4} lg={4}>
              <SkeletonPlaceholder className="kpi-skeleton" />
            </Column>
          ))}
        </Grid>
      </>
    );
  }
  const services = data?.services ?? [];
  const core = services.filter((s) => s.port < 8200);
  const mcp = services.filter((s) => s.port >= 8200);
  const renderGroup = (title: string, list: typeof services) => (
    <div className="dashboard-section">
      <p className="chart-tile__title">{title}</p>
      <Grid fullWidth className="stack-grid">
        {list.map((srv) => (
          <Column key={srv.name} sm={4} md={4} lg={4}>
            <Tile
              className={`service-tile ${
                srv.status === "offline"
                  ? "service-tile--offline"
                  : srv.status === "degraded"
                    ? "service-tile--degraded"
                    : ""
              }`}
            >
              <div className="service-tile__head">
                <span className="service-tile__name">{srv.name}</span>
                <StatusTag status={srv.status} />
              </div>
              <span className="service-tile__domain">{srv.domain}</span>
              <div className="service-tile__meta">
                <span>
                  Port <span className="mono">{srv.port}</span>
                </span>
                <span className="mono">HTTP · OpenTelemetry</span>
              </div>
            </Tile>
          </Column>
        ))}
      </Grid>
    </div>
  );
  return (
    <>
      <PageHeader
        title="System matrix"
        subtitle="Health-probe status and port mapping across the self-hosted telecom stack"
      />
      {renderGroup(`Core microservices (${core.length})`, core)}
      {renderGroup(`MCP servers (${mcp.length})`, mcp)}
    </>
  );
}
