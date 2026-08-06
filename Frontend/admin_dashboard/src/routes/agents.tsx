import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";
import { PageSection } from "@/components/nexus/app-topbar";
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { EmptyState, Segmented, TableShell, Td, Th, Token } from "@/components/nexus/primitives";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { AgentDetail } from "@/components/nexus/agent-detail";
import { getAgentActivity } from "@/lib/api/agents.server";
import { agentKeys } from "@/lib/nexus/query-keys";
import { errorMessage } from "@/lib/api/errors";
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
        content:
          "The persona graph: entry, specialists and terminal escalation, with observed activity.",
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

  const totalTurns = activity.data?.total_turns ?? 0;
  const rows = activity.data ? mergeAgentRows(activity.data.agents, totalTurns) : [];
  const unrecognized = rows.filter((row) => row.catalog === null);
  const idle = rows.filter((row) => row.catalog !== null && row.turns === 0);

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <HeroStat
          label="Caller turns"
          value={formatInteger(totalTurns)}
          context={`Across ${days} days`}
        />
        <StatCard
          label="Personas deployed"
          value={formatInteger(rows.length)}
          context="Catalog plus observed"
        />
        <StatCard
          label="Idle in window"
          value={formatInteger(idle.length)}
          context="No caller turns"
        />
        <StatCard
          label="Unrecognized"
          value={formatInteger(unrecognized.length)}
          context="Observed but not in catalog"
        />
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
              <Th align="right">Caller turns</Th>
              <Th align="right">Share</Th>
              <Th align="right">Sessions</Th>
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
                  onClick={() => setSelected(row)}
                  className="cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3"
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
                    <span className="t-mono text-ink-3">{formatInteger(row.turns)}</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{sharePercent(row.turnShare)}</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">{formatInteger(row.sessions)}</span>
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
