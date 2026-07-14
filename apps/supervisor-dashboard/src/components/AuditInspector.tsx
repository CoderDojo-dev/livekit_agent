import { useState } from "react";
import { Button, Column, Grid, InlineLoading, SkeletonPlaceholder, Tile } from "@carbon/react";
import { api } from "../api";
import { usePoll } from "../refresh";
import type { IntegrityReport } from "../types";
import { ErrorBanner, PageHeader, StatusTag } from "./shared";
export function AuditInspector() {
  const audit = usePoll(api.auditVerify);
  const [integrity, setIntegrity] = useState<IntegrityReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const runIntegrityJob = () => {
    setBusy(true);
    setJobError(null);
    api
      .integrityJob()
      .then((res) => setIntegrity(res))
      .catch((e: unknown) => setJobError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  const actions = busy ? (
    <InlineLoading description="Running cross-domain integrity check…" status="active" />
  ) : (
    <Button onClick={runIntegrityJob}>Run integrity audit job</Button>
  );
  return (
    <>
      <PageHeader
        title="Audit & integrity"
        subtitle="Cryptographic hash-chain ledger — entry_hash = sha256(previous_hash | canonical_payload | timestamp)"
        actions={actions}
      />
      {audit.error && <ErrorBanner title="Verification check failed" error={audit.error} />}
      {jobError && <ErrorBanner title="Integrity job failed" error={jobError} />}
      <Grid fullWidth className="stack-grid">
        <Column sm={4} md={4} lg={5}>
          {audit.data ? (
            <Tile
              className={`kpi-tile ${audit.data.intact ? "kpi-tile--success" : "kpi-tile--danger"}`}
            >
              <div>
                <p className="kpi-tile__label">Hash-chain status</p>
                <p className="kpi-tile__value">
                  {audit.data.intact ? "Intact" : "Tampered"}
                </p>
              </div>
              <p className="kpi-tile__hint">
                Verified via PgAuditLedger.verify() over all records
              </p>
            </Tile>
          ) : (
            <SkeletonPlaceholder className="kpi-skeleton" />
          )}
        </Column>
        <Column sm={4} md={4} lg={5}>
          {audit.data ? (
            <Tile className="kpi-tile kpi-tile--info">
              <div>
                <p className="kpi-tile__label">Audited events</p>
                <p className="kpi-tile__value">{audit.data.entries}</p>
              </div>
              <p className="kpi-tile__hint">
                Immutable hash-linked records in audit.audit_ledger
              </p>
            </Tile>
          ) : (
            <SkeletonPlaceholder className="kpi-skeleton" />
          )}
        </Column>
        <Column sm={4} md={8} lg={6}>
          <Tile className="chart-tile">
            <p className="chart-tile__title">Referential integrity report</p>
            {integrity ? (
              <div className="stat-list">
                <div className="stat-list__row">
                  <span>Orphan scan</span>
                  <StatusTag status={integrity.ok ? "resolved" : "failed"} />
                </div>
                <div className="stat-list__row">
                  <span>Audit chain matches</span>
                  <span className="stat-list__value">
                    {integrity.audit_chain_intact ? "Yes" : "No"}
                  </span>
                </div>
                <div className="stat-list__row">
                  <span>Audited rows</span>
                  <span className="stat-list__value">{integrity.audit_entries}</span>
                </div>
              </div>
            ) : (
              <p className="muted" style={{ fontSize: "0.8125rem" }}>
                Run the integrity audit job to scan Customer, Subscription, Invoice, Ticket and
                CallSession foreign keys for orphaned records, and to cross-check the hash chain.
              </p>
            )}
          </Tile>
        </Column>
      </Grid>
    </>
  );
}
