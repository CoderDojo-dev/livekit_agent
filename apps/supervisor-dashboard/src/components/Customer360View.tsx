import { useState } from "react";
import {
  Button,
  Column,
  Grid,
  InlineLoading,
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
import { api } from "../api";
import type { Customer360Data } from "../types";
import { ErrorBanner, PageHeader, StatusTag } from "./shared";
export function Customer360View() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Customer360Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fetchCustomer = () => {
    const id = query.trim();
    if (!id) return;
    setLoading(true);
    setError(null);
    api
      .customer360(id)
      .then(setData)
      .catch((e: unknown) => {
        setData(null);
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setLoading(false));
  };
  return (
    <>
      <PageHeader
        title="Customer 360"
        subtitle="Consolidated caller profile: SIM subscriptions, open TND invoices and GLPI support tickets"
      />
      <div className="inline-form">
        <TextInput
          id="customer-uuid"
          labelText="Customer UUID"
          placeholder="e.g. from a session dossier or CRM record"
          className="mono"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && fetchCustomer()}
        />
        {loading ? (
          <InlineLoading description="Searching…" status="active" />
        ) : (
          <Button renderIcon={Search} onClick={fetchCustomer}>
            Look up
          </Button>
        )}
      </div>
      {error && <ErrorBanner title="Lookup failed" error={error} />}
      {!data && !error && !loading && (
        <div className="table-empty">
          Enter a customer UUID above to load the full 360° dossier.
        </div>
      )}
      {data && (
        <>
          <Grid fullWidth className="stack-grid dashboard-section">
            <Column sm={4} md={4} lg={5}>
              <Tile className="kpi-tile kpi-tile--info">
                <div>
                  <p className="kpi-tile__label">Caller profile</p>
                  <p className="kpi-tile__value" style={{ fontSize: "1.5rem" }}>
                    {data.name}
                  </p>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <Tag size="sm" type="blue">
                    {data.preferred_language.toUpperCase()}
                  </Tag>
                  {data.vip ? (
                    <Tag size="sm" type="purple">
                      VIP
                    </Tag>
                  ) : (
                    <Tag size="sm" type="gray">
                      STANDARD
                    </Tag>
                  )}
                  <span className="mono muted" style={{ alignSelf: "center" }}>
                    {data.customer_id.slice(0, 13)}…
                  </span>
                </div>
              </Tile>
            </Column>
            <Column sm={4} md={4} lg={5}>
              <Tile className="chart-tile">
                <p className="chart-tile__title">
                  Active subscriptions ({data.subscriptions.length})
                </p>
                <div className="stat-list">
                  {data.subscriptions.map((sub) => (
                    <div className="stat-list__row" key={sub.subscription_id}>
                      <span>
                        <span className="mono">{sub.msisdn}</span>
                        <span className="muted"> · {sub.plan}</span>
                      </span>
                      <StatusTag status={sub.status} />
                    </div>
                  ))}
                  {data.subscriptions.length === 0 && (
                    <span className="muted">No active SIM lines registered.</span>
                  )}
                </div>
              </Tile>
            </Column>
            <Column sm={4} md={8} lg={6}>
              <Tile className="chart-tile">
                <p className="chart-tile__title">
                  Open invoices ({data.open_invoices.length})
                </p>
                <div className="stat-list">
                  {data.open_invoices.map((inv) => (
                    <div className="stat-list__row" key={inv.invoice}>
                      <span>
                        <span className="mono">{inv.invoice}</span>
                        <span className="muted"> · {inv.status}</span>
                      </span>
                      <span className="stat-list__value">{inv.amount.toFixed(3)} TND</span>
                    </div>
                  ))}
                  {data.open_invoices.length === 0 && (
                    <span className="muted">All invoices settled — 0.000 TND due.</span>
                  )}
                </div>
              </Tile>
            </Column>
          </Grid>
          <TableContainer
            title={`GLPI support tickets (${data.tickets.length})`}
            description="Tickets synchronised from the GLPI MCP adapter"
          >
            <Table size="lg">
              <TableHead>
                <TableRow>
                  <TableHeader>Ticket ID</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Subject</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.tickets.map((tk) => (
                  <TableRow key={tk.glpi_id}>
                    <TableCell>
                      <strong className="mono">{tk.glpi_id}</strong>
                    </TableCell>
                    <TableCell>
                      <Tag size="sm" type="blue">
                        {tk.status}
                      </Tag>
                    </TableCell>
                    <TableCell>{tk.subject}</TableCell>
                  </TableRow>
                ))}
                {data.tickets.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3}>
                      <span className="muted">No GLPI tickets logged for this caller.</span>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </>
  );
}
