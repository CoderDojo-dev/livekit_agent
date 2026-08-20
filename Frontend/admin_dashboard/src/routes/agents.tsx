import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bot, Clock, Coins, Layers, PhoneCall } from "lucide-react";
import { pageTitle } from "@/lib/nexus/brand";
import { PageSection } from "@/components/nexus/app-topbar";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { EmptyState, Segmented, TableShell, Td, Th, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState, TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { AgentDetail } from "@/components/nexus/agent-detail";
import {
  AgentActivitySparkline,
  type AgentSparklineMetric,
} from "@/components/nexus/agent-activity-sparkline";
import { getAgentActivity } from "@/lib/api/agents.server";
import { agentKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";
import {
  formatDuration,
  formatLastSeen,
  mergeAgentRows,
  providerTokenTotal,
  routesLabel,
  type AgentRow,
} from "@/lib/nexus/agent-view";

const WINDOWS = [7, 14, 30] as const;

export const Route = createFileRoute("/agents")({
  head: () => ({
    meta: [
      { title: pageTitle("Agents") },
      {
        name: "description",
        content: "AI persona activity and provider token telemetry for the selected window.",
      },
    ],
  }),
  component: AgentsPage,
});

export function AgentsPage() {
  const [days, setDays] = useState<number>(30);
  const [metric, setMetric] = useState<AgentSparklineMetric>("duration");
  const [selected, setSelected] = useState<AgentRow | null>(null);
  const [page, setPage] = useState(0);

  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 560,
    min: 5,
    max: 12,
    fallback: 8,
  });

  const activity = useQuery({
    queryKey: agentKeys.activity(days),
    queryFn: () => getAgentActivity({ data: { days } }),
  });

  const rows = activity.data
    ? mergeAgentRows(
        activity.data.personas,
        activity.data.totals.persona_call_attributions,
        activity.data.window,
      )
    : [];

  useEffect(() => setPage(0), [days, pageSize]);
  const safePage = clampPage(page, rows.length, pageSize);
  const pageRows = slicePage(rows, safePage, pageSize);

  return (
    <>
      <PageSection index={0} className="grid gap-sp-6 xl:grid-cols-4">
        {activity.isPending ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : activity.isError ? (
          <div className="xl:col-span-4">
            <ErrorState error={activity.error} onRetry={() => void activity.refetch()} />
          </div>
        ) : (
          <>
            <HeroStat
              label="Unique calls"
              value={formatInteger(activity.data.totals.global_unique_calls)}
              context={`${activity.data.window.days} days / UTC`}
              icon={PhoneCall}
            />
            <StatCard
              label="Persona-call attributions"
              value={formatInteger(activity.data.totals.persona_call_attributions)}
              context="One call may be attributed to multiple AI personas"
              icon={Layers}
            />
            <StatCard
              label="Attributed call duration"
              value={formatDuration(activity.data.totals.attributed_call_duration_seconds)}
              context="Non-exclusive whole-call attribution"
              icon={Clock}
            />
            <StatCard
              label="Provider tokens"
              value={
                activity.data.totals.provider_input_tokens === null &&
                activity.data.totals.provider_output_tokens === null
                  ? "Unavailable"
                  : formatInteger(
                      (activity.data.totals.provider_input_tokens ?? 0) +
                        (activity.data.totals.provider_output_tokens ?? 0),
                    )
              }
              context="Provider-reported, forward-only"
              icon={Coins}
            />
          </>
        )}
      </PageSection>

      <PageSection index={1}>
        <TableShell
          minWidth={1180}
          bodyAsChild
          busy={activity.isFetching && !activity.isPending}
          toolbar={
            <>
              <Segmented
                groupId="agent-window"
                items={WINDOWS.map((value) => `${value}d`)}
                active={`${days}d`}
                onSelect={(label) => setDays(Number(label.replace("d", "")))}
              />
              <Segmented
                groupId="agent-metric"
                items={["Duration", "Tokens"]}
                active={metric === "duration" ? "Duration" : "Tokens"}
                onSelect={(label) => setMetric(label === "Tokens" ? "tokens" : "duration")}
              />
            </>
          }
          head={
            <tr>
              <Th>AI persona</Th>
              <Th>Role in graph</Th>
              <Th align="right">Attributed calls</Th>
              <Th align="right">Attributed duration</Th>
              <Th align="right">Trend</Th>
              <Th align="right">Provider tokens</Th>
              <Th align="right">Last observed</Th>
            </tr>
          }
          footer={
            <Pager
              page={safePage}
              pageSize={pageSize}
              total={rows.length}
              onPageChange={setPage}
              noun="personas"
              busy={activity.isFetching && !activity.isPending}
              className="w-full"
            />
          }
        >
          <TableBodySwap pageKey={`${safePage}-${days}`}>
            {activity.isPending ? <TableSkeleton rows={pageSize} columns={7} /> : null}

            {activity.isError ? (
              <TableErrorRow
                columns={7}
                error={activity.error}
                onRetry={() => activity.refetch()}
              />
            ) : null}

            {activity.isSuccess && activity.data.personas.length === 0 ? (
              <tr>
                <td colSpan={7} className="h-[52px] border-b border-stroke-subtle px-sp-6">
                  <EmptyState
                    icon={Bot}
                    title="No AI persona activity"
                    description="No persona-call attribution or provider token event exists in this window."
                  />
                </td>
              </tr>
            ) : null}

            {activity.isSuccess
              ? pageRows.map((row) => (
                  <tr
                    key={row.className}
                    role="button"
                    tabIndex={0}
                    onClick={(event) => {
                      if (
                        event.target !== event.currentTarget &&
                        (event.target as HTMLElement).closest(
                          "a, button, input, select, textarea, [role='button']",
                        )
                      ) {
                        return;
                      }

                      setSelected(row);
                    }}
                    onKeyDown={(event) => {
                      if (event.target !== event.currentTarget) return;

                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelected(row);
                      }
                    }}
                    className="cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-n-12"
                  >
                    <Td>
                      <span className="min-w-0">
                        <span className="t-ui block truncate text-ink-1">{row.label}</span>
                        <span className="t-caption block truncate text-ink-4">{row.className}</span>
                      </span>
                    </Td>
                    <Td>
                      {row.catalog === null ? (
                        <Token mono={false}>Unrecognized</Token>
                      ) : (
                        <span className="flex items-center gap-sp-4">
                          {row.catalog.entryPoint ? (
                            <Token mono={false} strong>
                              Entry point
                            </Token>
                          ) : null}
                          <Token mono={false}>{routesLabel(row.catalog)}</Token>
                        </span>
                      )}
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {formatInteger(row.attributedCalls)}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {formatDuration(row.attributedCallDurationSeconds)}
                      </span>
                    </Td>
                    <Td align="right">
                      <AgentActivitySparkline
                        points={row.daily}
                        metric={metric}
                        label={`${row.label} ${
                          metric === "duration" ? "attributed call duration" : "provider token"
                        } trend over ${activity.data.window.days} days`}
                      />
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {providerTokenTotal(row) === null
                          ? "Unavailable"
                          : formatInteger(providerTokenTotal(row) ?? 0)}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {formatLastSeen(row.lastObservedAt)}
                      </span>
                    </Td>
                  </tr>
                ))
              : null}
          </TableBodySwap>
        </TableShell>
      </PageSection>

      {selected ? (
        <AgentDetail row={selected} metric={metric} onClose={() => setSelected(null)} />
      ) : null}
    </>
  );
}
