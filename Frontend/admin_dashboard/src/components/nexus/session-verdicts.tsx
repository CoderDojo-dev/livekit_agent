import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import { Card, CardHeader, EmptyState, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { listSessionVerdicts } from "@/lib/api/supervision.server";
import {
  isBlockingVerdict,
  isEscalateVerdict,
  sessionVerdictLabel,
  verdictSequence,
} from "@/lib/nexus/supervision-view";
import { queryKeys } from "@/lib/nexus/query-keys";
import { cn } from "@/lib/utils";

/**
 * Policy verdicts for one call, chronological.
 *
 * GET /api/v1/policy/verdicts had no client before this component; the cache key
 * queryKeys.supervision.verdicts() was already declared for it. The projection has no
 * timestamps, so order is conveyed by the step number and never by a rendered time.
 */
export function SessionVerdicts({ sessionId }: { sessionId: string }) {
  const query = useQuery({
    queryKey: queryKeys.supervision.verdicts(sessionId),
    queryFn: () => listSessionVerdicts({ data: { sessionId } }),
    enabled: Boolean(sessionId),
  });

  const rows = verdictSequence(query.data?.verdicts ?? []);

  return (
    <Card padded={false}>
      <div className="flex items-center justify-between gap-sp-5 p-sp-7">
        <CardHeader
          title="Policy verdicts"
          subtitle="Every gate decision taken during this call, in order."
        />
        {query.data ? (
          <span className="t-caption text-ink-5">
            {rows.length} {rows.length === 1 ? "verdict" : "verdicts"}
          </span>
        ) : null}
      </div>

      {query.isPending ? (
        <div className="p-sp-7">
          <CardSkeleton lines={3} />
        </div>
      ) : query.isError ? (
        <div className="p-sp-7">
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        </div>
      ) : rows.length === 0 ? (
        <div className="p-sp-7">
          <EmptyState
            icon={Scale}
            title="No verdicts"
            description="The policy engine was never consulted on this call."
          />
        </div>
      ) : (
        <ul className="border-t border-stroke-subtle">
          {rows.map((v) => (
            <li
              key={v.id}
              className={cn(
                "border-b border-stroke-subtle px-sp-7 py-sp-5 last:border-b-0",
                isBlockingVerdict(v.verdict) && "bg-surface-3/40",
              )}
            >
              <div className="flex flex-wrap items-center gap-sp-4">
                <Token>{String(v.step)}</Token>
                <span className="t-ui text-ink-1">{v.action}</span>
                <Token strong={isEscalateVerdict(v.verdict)}>
                  {sessionVerdictLabel(v.verdict)}
                </Token>
                <Token className="ml-auto">{v.rule_id}</Token>
              </div>
              <p className="t-caption mt-sp-3 text-ink-3">{v.justification}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
