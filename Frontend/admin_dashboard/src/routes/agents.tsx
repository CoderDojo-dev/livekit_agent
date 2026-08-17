import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageSection } from "@/components/nexus/app-topbar";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { EmptyState, Segmented, TableShell, Td, Th, Token } from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState, TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { AgentDetail } from "@/components/nexus/agent-detail";
import { getAgentActivity } from "@/lib/api/agents.server";
import { agentKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";
import {
  formatLastSeen,
  mergeAgentRows,
  routesLabel,
  sharePercent,
  type AgentRow,
} from "@/lib/nexus/agent-view";

const WINDOWS = [7, 14, 30] as const;

export const Route = createFileRoute("/agents")({
  head: () => ({
    meta: [
      { title: "Agents \u2014 Nexus" },
      {
        name: "description",
        content: "Agent catalog entries and observed activity for the selected window.",
      },
    ],
  }),
  component: AgentsPage,
});

function AgentsPage() {
  const [days, setDays] = useState<number>(30);
  const [selected, setSelected] = useState<AgentRow | null>(null);

  const activity = useQuery({
    queryKey: agentKeys.activity(days),
    queryFn: () => getAgentActivity({ data: { days } }),
  });

  const rows = activity.data ? mergeAgentRows(activity.data.agents, activity.data.total_sessions) : [];
  const unrecognized = rows.filter((row) => row.catalog === null);
  const idle = rows.filter((row) => row.catalog !== null && row.turns === 0);

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
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
              label="Agent sessions"
              value={formatInteger(activity.data.total_sessions)}
              context={`${Math.round(activity.data.total_duration_seconds / 60)} persisted minutes`}
            />
            <StatCard
              label="Time spent"
              value={`${Math.round(activity.data.total_duration_seconds / 60)}m`}
              context="Sum of persisted session durations"
            />
            <StatCard
              label="Input tokens"
              value={activity.data.input_tokens === null ? "Unavailable" : formatInteger(activity.data.input_tokens)}
              context="Provider-reported; forward-only"
            />
            <StatCard
              label="Output tokens"
              value={activity.data.output_tokens === null ? "Unavailable" : formatInteger(activity.data.output_tokens)}
              context="No historical backfill"
            />
          </>
        )}
      </PageSection>

      <PageSection>
        <TableShell
          toolbar={
            <Segmented
              items={WINDOWS.map((value) => `${value}d`)}
              active={`${days}d`}
              onSelect={(label) => setDays(Number(label.replace("d", "")))}
            />
          }
          head={
            <tr>
              <Th>Persona</Th>
              <Th>Role in graph</Th>
              <Th align="right">Time spent</Th>
              <Th align="right">Avg duration</Th>
              <Th align="right">Tokens</Th>
              <Th align="right">Last seen</Th>
            </tr>
          }
        >
          {activity.isPending ? <TableSkeleton rows={5} columns={6} /> : null}

          {activity.isError ? (
            <TableErrorRow columns={6} error={activity.error} onRetry={() => activity.refetch()} />
          ) : null}

          {activity.isSuccess && rows.length === 0 ? (
            <tr>
              <td colSpan={6} className="h-[52px] border-b border-stroke-subtle px-sp-6">
                <EmptyState
                  icon={Bot}
                  title="No persona activity"
                  description="No caller turns were handled by a persona in this window."
                />
              </td>
            </tr>
          ) : null}

          {activity.isSuccess
            ? rows.map((row) => (
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
                    <span className="t-mono text-ink-3">{Math.round(row.durationSeconds / 60)}m</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{row.averageDurationSeconds === null ? "ΓÇö" : `${Math.round(row.averageDurationSeconds)}s`}</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{row.totalTokens === null ? "Unavailable" : formatInteger(row.totalTokens)}</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{formatLastSeen(row.lastSeen)}</span>
                  </Td>
                </tr>
              ))
            : null}
        </TableShell>
      </PageSection>

      {selected ? <AgentDetail row={selected} onClose={() => setSelected(null)} /> : null}
    </>
  );
}
