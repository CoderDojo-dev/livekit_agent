import { Modal } from "@/components/nexus/modal";
import { CardHeader, StatusChip, Token } from "@/components/nexus/primitives";
import { actionStatusKey, formatInstant, verdictLabel } from "@/lib/nexus/decision-view";
import type { Decision } from "@/lib/api/decisions.server";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-sp-5 py-sp-4 first:pt-0 last:pb-0">
      <span className="t-label shrink-0 text-ink-3">{label}</span>
      <span className="min-w-0 flex-1 text-right">{children}</span>
    </div>
  );
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="py-sp-4 first:pt-0">
      <p className="t-label text-ink-3">{label}</p>
      <pre className="t-mono-s mt-sp-3 max-h-[180px] overflow-auto whitespace-pre-wrap break-words rounded-r-2 border border-stroke-subtle bg-surface-1 p-sp-4 text-ink-2">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </div>
  );
}

/** G5 — the detail modal. The Modal component portals to document.body (Feature 1 fix), so the
 *  overlay is never clipped by PageSection's `.rise` containing block. */
export function DecisionDetail({
  decision,
  onClose,
  showCallLink,
}: {
  decision: Decision | null;
  onClose: () => void;
  showCallLink: boolean;
}) {
  return (
    <Modal
      open={decision !== null}
      onClose={onClose}
      title={decision ? `${verdictLabel(decision.verdict)} · ${decision.action}` : ""}
      description={
        decision ? `Rule ${decision.rule_id} · ${formatInstant(decision.created_at)}` : ""
      }
    >
      {decision ? (
        <div className="flex flex-col divide-y divide-stroke-subtle">
          <Row label="Justification">
            <p className="t-ui text-left text-ink-2">{decision.justification}</p>
          </Row>

          <Row label="Session">
            {showCallLink ? (
              <a
                className="t-mono break-all text-ink-1 underline decoration-dotted decoration-from-font underline-offset-4 hover:text-ink-4"
                href={`/calls?session=${encodeURIComponent(decision.session_id)}`}
              >
                {decision.session_id}
              </a>
            ) : (
              <span className="t-mono break-all text-ink-1">{decision.session_id}</span>
            )}
          </Row>

          <Row label="Customer">
            <span className="t-mono text-ink-2">
              {decision.customer_id ? decision.customer_id : "\u2014"}
            </span>
          </Row>

          <Row label="Direction">
            <Token>{decision.direction}</Token>
          </Row>

          <JsonBlock label="Inputs snapshot (evidence used)" value={decision.inputs_snapshot} />

          {/* G4 — the reason this page exists: what broke and how many times. */}
          <div className="py-sp-4">
            <CardHeader title="Actions" subtitle="What the engine actually executed." />
            <ul className="mt-sp-5 flex flex-col gap-sp-5">
              {decision.actions.length === 0 ? (
                <li>
                  <p className="t-caption text-ink-5">No actions were recorded for this verdict.</p>
                </li>
              ) : (
                decision.actions.map((action) => (
                  <li
                    key={action.id}
                    className="rounded-r-2 border border-stroke-subtle bg-surface-1 p-sp-5"
                  >
                    <div className="flex items-center justify-between gap-sp-5">
                      <span className="t-ui text-ink-1">{action.action_type}</span>
                      <StatusChip status={actionStatusKey(action.status)} />
                    </div>
                    <p className="t-caption mt-sp-2 text-ink-4">
                      {action.target_domain} · attempted {action.attempt_count}
                    </p>
                    {action.error_message ? (
                      <p className="t-caption mt-sp-3 text-ink-2">{action.error_message}</p>
                    ) : (
                      <p className="t-caption mt-sp-3 text-ink-5">No error recorded.</p>
                    )}
                    <div className="mt-sp-4 flex flex-wrap items-center gap-sp-4">
                      <Token>{action.idempotency_key}</Token>
                      {action.reference ? <Token>{action.reference}</Token> : null}
                      <span className="t-mono-s ml-auto text-ink-4">
                        {formatInstant(action.created_at)}
                      </span>
                    </div>
                    <div className="mt-sp-4">
                      <p className="t-micro mb-sp-2 font-medium text-ink-5">Parameters</p>
                      <pre className="t-mono-s max-h-[160px] overflow-auto whitespace-pre-wrap break-words rounded-r-2 bg-surface-2 p-sp-4 text-ink-3">
                        {JSON.stringify(action.parameters ?? {}, null, 2)}
                      </pre>
                    </div>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
