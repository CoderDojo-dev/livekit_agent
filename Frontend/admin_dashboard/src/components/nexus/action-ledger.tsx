import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
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
const SCOPES: Array<{ id: LedgerActionStatus; label: string }> = [
  { id: "failed", label: "Failed" },
  { id: "retrying", label: "Retrying" },
  { id: "pending", label: "Pending" },
  { id: "succeeded", label: "Succeeded" },
];

export function ActionLedgerPanel() {
  const [status, setStatus] = useState<LedgerActionStatus>("failed");

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
            icon={Activity}
            title="Nothing in this state"
            description="No action in the ledger currently carries this status."
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
