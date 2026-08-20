import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ListChecks, Scale } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";
import { DecisionDetail } from "@/components/nexus/decision-detail";
import { ActionLedgerPanel } from "@/components/nexus/action-ledger";
import { getVerdictDistribution, listDecisions, type Decision } from "@/lib/api/decisions.server";
import {
  actionRollup,
  decisionMatches,
  distributionTotals,
  formatInstant,
  hasFailure,
  isEscalate,
  truncate,
  verdictLabel,
} from "@/lib/nexus/decision-view";
import { decisionKeys } from "@/lib/nexus/query-keys";
import { cn } from "@/lib/utils";

const VERDICT_OPTIONS = [
  { id: "all", label: "All" },
  { id: "AUTHORIZED", label: "Authorized" },
  { id: "REFUSED", label: "Refused" },
  { id: "ESCALATE", label: "Escalate" },
];

const COLUMN_COUNT = 6;

export const Route = createFileRoute("/decisions")({
  head: () => ({
    meta: [
      { title: pageTitle("Decisions") },
      {
        name: "description",
        content:
          "Every policy verdict with the actions it authorized — the decision and its consequence.",
      },
      { property: "og:title", content: pageTitle("Decisions") },
      { property: "og:description", content: "The policy verdict ledger and its action chain." },
    ],
  }),
  component: DecisionsPage,
});

function DecisionsPage() {
  const [verdict, setVerdict] = useState<"all" | "AUTHORIZED" | "REFUSED" | "ESCALATE">("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  /* Decision rows stack a Token under the action name, so they run taller than a plain table
   * row — the page size is derived from the stacked height, not the 52px default. This page
   * previously rendered EVERY row the server returned with no limiting affordance at all. */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.stacked,
    chrome: 620,
    min: 5,
    max: 10,
    fallback: 6,
  });

  const query = useQuery({
    queryKey: decisionKeys.list(verdict),
    queryFn: () => listDecisions({ data: { verdict: verdict === "all" ? undefined : verdict } }),
  });

  const distributionQuery = useQuery({
    queryKey: decisionKeys.distribution(),
    queryFn: () => getVerdictDistribution(),
  });

  const rows = useMemo(
    () => (query.data?.decisions ?? []).filter((d) => decisionMatches(d, search)),
    [query.data, search],
  );

  useEffect(() => setPage(0), [verdict, search, pageSize]);
  const safePage = clampPage(page, rows.length, pageSize);
  const visible = slicePage(rows, safePage, pageSize);

  /* Resolved against the whole filtered set so an open detail survives a page change. */
  const selected: Decision | undefined = rows.find((d) => d.id === selectedId);

  return (
    <PageSection>
      {/* G10 — verdict distribution from telemetry_timeline, capped at last 100 verdicts.
          Rendered via Card + Token, never StatCard: there is no delta in this data. */}
      <Card className="mb-sp-6">
        <CardHeader
          title="Verdict distribution"
          subtitle="Across the most recent 100 decisions."
          icon={Scale}
        />
        <div className="mt-sp-6 flex flex-wrap items-center gap-sp-5">
          {(["AUTHORIZED", "REFUSED", "ESCALATE"] as const).map((v) => (
            <span key={v} className="flex items-center gap-sp-3">
              <Token strong={isEscalate(v)}>{verdictLabel(v)}</Token>
              <span className="t-mono text-ink-2">
                {distributionQuery.data?.verdict_distribution[
                  v.toLowerCase() as keyof typeof distributionQuery.data.verdict_distribution
                ] ?? 0}
              </span>
            </span>
          ))}
          <span className="t-caption ml-auto text-ink-5">
            {distributionTotals(distributionQuery.data?.verdict_distribution)} decisions in the
            window
          </span>
        </div>
      </Card>

      <ActionLedgerPanel />

      <TableShell
        minWidth={980}
        bodyAsChild
        busy={query.isFetching && !query.isPending}
        toolbar={
          <div className="flex flex-1 items-center gap-sp-5">
            <SearchInput
              placeholder="Search decisions"
              className="w-[260px]"
              value={search}
              onChange={setSearch}
            />
            <Segmented
              items={VERDICT_OPTIONS.map((o) => o.label)}
              active={VERDICT_OPTIONS.find((o) => o.id === verdict)?.label ?? "All"}
              groupId="decision-verdict"
              onSelect={(label) => {
                setVerdict(
                  VERDICT_OPTIONS.find((o) => o.label === label)?.id as
                    "all" | "AUTHORIZED" | "REFUSED" | "ESCALATE",
                );
                setSelectedId(null);
              }}
            />
          </div>
        }
        head={
          <tr>
            <Th>Decision</Th>
            <Th>Verdict</Th>
            <Th>Rule</Th>
            <Th>Justification</Th>
            <Th>Actions</Th>
            <Th align="right">When</Th>
          </tr>
        }
        footer={
          <Pager
            page={safePage}
            pageSize={pageSize}
            total={rows.length}
            onPageChange={setPage}
            noun="decisions"
            busy={query.isFetching && !query.isPending}
            className="w-full"
          />
        }
      >
        <TableBodySwap pageKey={`${safePage}-${verdict}`}>
          {query.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
          ) : query.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={query.error}
              onRetry={() => void query.refetch()}
            />
          ) : query.data && query.data.decisions.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={Scale}
                  title="No decisions recorded"
                  description="The policy engine has not recorded a verdict in this scope."
                />
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={Scale}
                  title="No matching decisions"
                  description="Nothing in this ledger matches your search."
                />
              </td>
            </tr>
          ) : (
            visible.map((d) => (
              <tr
                key={d.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedId(d.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedId(d.id);
                  }
                }}
                className={cn(
                  "cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3",
                  hasFailure(d) && "bg-surface-3/40",
                )}
              >
                <Td>
                  <span className="t-ui text-ink-1">{d.action}</span>
                  <span className="mt-sp-2 block">
                    <Token>{d.direction}</Token>
                  </span>
                </Td>
                <Td>
                  <Token strong={isEscalate(d.verdict)}>{verdictLabel(d.verdict)}</Token>
                </Td>
                <Td>
                  <Token>{d.rule_id}</Token>
                </Td>
                <Td>
                  <span className="t-caption text-ink-3">{truncate(d.justification, 64)}</span>
                </Td>
                <Td>
                  <span className="t-caption text-ink-3">{actionRollup(d)}</span>
                  {hasFailure(d) ? (
                    <span className="mt-sp-2 block">
                      <StatusChip status="failed" />
                    </span>
                  ) : null}
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">{formatInstant(d.created_at)}</span>
                </Td>
              </tr>
            ))
          )}
        </TableBodySwap>
      </TableShell>

      <DecisionDetail
        decision={selected ?? null}
        onClose={() => setSelectedId(null)}
        /* G7 — Feature 4 is applied; calls.tsx resolves /calls?session=<uuid>. */
        showCallLink={true}
      />
    </PageSection>
  );
}
