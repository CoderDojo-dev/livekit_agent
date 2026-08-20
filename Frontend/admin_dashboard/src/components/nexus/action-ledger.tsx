import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2 } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { listLedgerActions, type LedgerActionStatus } from "@/lib/api/supervision.server";
import { actionStatusKey } from "@/lib/nexus/decision-view";
import { actionScopeLabel } from "@/lib/nexus/supervision-view";
import { queryKeys } from "@/lib/nexus/query-keys";

/**
 * The execution action ledger, filtered by status.
 *
 * NOT the same data as the Actions column on the decisions table: that column is scoped to the
 * last 100 verdicts, whereas this route scans the whole ledger for one status. The projection
 * carries no attempt_count, error_message or timestamp, so nothing here renders them.
 * Status chips reuse actionStatusKey() — no new key is added to status.ts.
 */
/* Succeeded first, and selected by default.
 *
 * The panel used to open on "Failed", so on a healthy platform it greeted every visitor with an
 * empty state — which read as "this component is broken" rather than "nothing has failed".
 * (Confirmed against the live ledger: 12 succeeded rows, 0 failed.) Opening on Succeeded shows
 * the ledger working; the failure scopes are one click away and are where you go when something
 * is actually wrong. */
const SCOPES: Array<{ id: LedgerActionStatus; label: string }> = [
  { id: "succeeded", label: "Succeeded" },
  { id: "failed", label: "Failed" },
  { id: "retrying", label: "Retrying" },
  { id: "pending", label: "Pending" },
];

export function ActionLedgerPanel() {
  const [status, setStatus] = useState<LedgerActionStatus>("succeeded");

  const query = useQuery({
    queryKey: queryKeys.supervision.actions(status),
    queryFn: () => listLedgerActions({ data: { status } }),
  });

  const rows = query.data?.actions ?? [];

  return (
    <Card className="mb-sp-6">
      <CardHeader
        title="Action ledger"
        subtitle="Every execution attempt carrying this status, across the whole ledger."
        action={
          <Segmented
            items={SCOPES.map((s) => s.label)}
            active={SCOPES.find((s) => s.id === status)!.label}
            onSelect={(label) => {
              const next = SCOPES.find((s) => s.label === label);
              if (next) setStatus(next.id);
            }}
          />
        }
      />

      {query.isPending ? (
        <div className="mt-sp-6">
          <CardSkeleton lines={3} />
        </div>
      ) : query.isError ? (
        <div className="mt-sp-6">
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-sp-6">
          <EmptyState
            icon={status === "succeeded" ? Activity : CheckCircle2}
            title={status === "succeeded" ? "No executed actions yet" : `No ${status} actions`}
            /* An empty FAILURE scope is good news and should say so. An empty success scope means
             * the platform genuinely has not executed anything, which is a different fact. */
            description={
              status === "succeeded"
                ? "The execution service has not completed an action yet. Actions appear here once a policy verdict authorizes one."
                : "Nothing in the ledger carries this status — on a healthy platform that is the expected state."
            }
          />
        </div>
      ) : (
        <>
          <ul className="mt-sp-6 flex flex-col gap-sp-4">
            {rows.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center gap-sp-4 rounded-r-2 border border-stroke-subtle bg-surface-1 p-sp-5"
              >
                <span className="t-ui text-ink-1">{a.action_type}</span>
                <StatusChip status={actionStatusKey(a.status)} />
                <Token className="ml-auto">{a.idempotency_key}</Token>
                {a.reference ? <Token>{a.reference}</Token> : null}
              </li>
            ))}
          </ul>
          <p className="t-caption mt-sp-5 text-ink-5">{actionScopeLabel(status, rows.length)}</p>
        </>
      )}
    </Card>
  );
}
