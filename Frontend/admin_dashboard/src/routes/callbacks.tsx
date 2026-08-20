import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PhoneOff } from "lucide-react";

import { PageSection } from "@/components/nexus/app-topbar";
import {
  Avatar,
  Button,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { NoteBanner } from "@/components/nexus/note-banner";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";
import { CallbackCancelModal, CallbackOutcomeModal } from "@/components/nexus/callback-outcome";
import { CallbackLifecycleModal } from "@/components/nexus/callback-lifecycle";
import { getCoverage } from "@/lib/api/availability.server";
import { getCallbackStats, listCallbacks, type Callback } from "@/lib/api/callbacks.server";
import { callbackKeys, availabilityKeys } from "@/lib/nexus/query-keys";
import {
  CALLBACK_SCOPES,
  callbackCustomer,
  callbackMatches,
  callbackStatusKey,
  formatBusinessDayTime,
  priorityLabel,
  scopeQuery,
  scopeTotal,
  type CallbackScope,
} from "@/lib/nexus/callback-view";
import { initials } from "@/lib/nexus/format";

const COLUMN_COUNT = 8;

/**
 * The queue is fetched once at a fixed depth and paged in memory.
 *
 * The page used to expose a 100/250/500 selector built out of `Segmented` — the control that
 * means "filter scope" everywhere else in the product — and 500 rows at 52px produced a
 * ~26 000px page, roughly twenty-nine screens. The depth is now a constant and the reader moves
 * through it with the pager, which is both shorter and honest about how much was fetched.
 */
const FETCH_DEPTH = 250;

export const Route = createFileRoute("/callbacks")({
  head: () => ({
    meta: [{ title: pageTitle("Callbacks") }],
  }),
  component: CallbacksPage,
});

function CallbacksPage() {
  const [scope, setScope] = useState<CallbackScope>("pending");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [outcomeFor, setOutcomeFor] = useState<Callback | null>(null);
  const [cancelFor, setCancelFor] = useState<Callback | null>(null);
  const [detailFor, setDetailFor] = useState<Callback | null>(null);

  const { status, overdueOnly } = scopeQuery(scope);

  const listQuery = useQuery({
    queryKey: callbackKeys.list(status, overdueOnly, FETCH_DEPTH),
    queryFn: () => listCallbacks({ data: { status, overdueOnly, limit: FETCH_DEPTH } }),
  });

  const statsQuery = useQuery({
    queryKey: callbackKeys.stats(),
    queryFn: () => getCallbackStats(),
  });

  // Callbacks carry no business-local string, and the queue endpoints never state their zone.
  // coverage_report is the backend's own answer for CALLBACK_TIMEZONE (see F3b).
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });

  const timeZone = coverageQuery.data?.timezone ?? "UTC";
  const zoneKnown = Boolean(coverageQuery.data?.timezone);

  const rows = listQuery.data ?? [];
  const visible = useMemo(() => rows.filter((row) => callbackMatches(row, query)), [rows, query]);

  const total = scopeTotal(scope, statsQuery.data);
  const truncated = rows.length >= FETCH_DEPTH;

  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 470,
    min: 5,
    max: 12,
    fallback: 8,
  });

  useEffect(() => setPage(0), [scope, query, pageSize]);
  const safePage = clampPage(page, visible.length, pageSize);
  const pageRows = slicePage(visible, safePage, pageSize);

  return (
    <PageSection index={0}>
      {/* Queue health as real counters rather than a run-on caption line. */}
      <div className="mb-sp-6 grid gap-sp-4 sm:grid-cols-[repeat(3,minmax(0,180px))_1fr]">
        {(
          [
            ["Pending", statsQuery.data?.pending],
            ["Overdue", statsQuery.data?.overdue],
            ["Completed", statsQuery.data?.completed],
          ] as const
        ).map(([label, value]) => (
          <div
            key={label}
            className="rounded-r-3 border border-stroke-subtle bg-surface-1 px-sp-6 py-sp-5"
          >
            <p className="t-micro text-ink-5">{label}</p>
            {value === undefined ? (
              <span className="shimmer mt-sp-3 block h-[18px] w-[48px] rounded-r-1" />
            ) : (
              <p className="t-metric-m mt-sp-2 text-ink-1">{value}</p>
            )}
          </div>
        ))}
        <div className="flex items-center sm:justify-end">
          <span className="t-caption text-ink-5">
            {zoneKnown
              ? `Times in ${timeZone}`
              : "Business timezone unavailable — times shown in UTC"}
          </span>
        </div>
      </div>

      <TableShell
        minWidth={1080}
        bodyAsChild
        busy={listQuery.isFetching && !listQuery.isPending}
        toolbar={
          <div className="flex w-full items-center justify-between gap-sp-5">
            <div className="flex items-center gap-sp-5">
              <Segmented
                groupId="callback-scope"
                items={CALLBACK_SCOPES.map((s) => s.label)}
                active={CALLBACK_SCOPES.find((s) => s.id === scope)!.label}
                onSelect={(label) => setScope(CALLBACK_SCOPES.find((s) => s.label === label)!.id)}
              />
              <div className="w-[260px]">
                <SearchInput
                  placeholder="Search caller, advisor, reason…"
                  value={query}
                  onChange={setQuery}
                />
              </div>
            </div>
          </div>
        }
        head={
          <tr>
            <Th>Caller</Th>
            <Th>Scheduled</Th>
            <Th>Window</Th>
            <Th>Reason</Th>
            <Th>Advisor</Th>
            <Th>Attempts</Th>
            <Th>Status</Th>
            <Th> </Th>
          </tr>
        }
        footer={
          <div className="w-full">
            <Pager
              page={safePage}
              pageSize={pageSize}
              total={visible.length}
              onPageChange={setPage}
              noun="callbacks"
              busy={listQuery.isFetching && !listQuery.isPending}
            />
            {/* The fetch depth is a real ceiling, so say so rather than implying the pager walks
             * the entire queue. */}
            <p className="t-caption mt-sp-3 text-ink-5">
              {truncated
                ? total !== null
                  ? `Deepest ${FETCH_DEPTH} of ${total} in this scope · narrow the search to reach the rest`
                  : `Deepest ${FETCH_DEPTH} in this scope · narrow the search to reach the rest`
                : "Ordered by priority, then soonest first"}
            </p>
          </div>
        }
      >
        <TableBodySwap pageKey={`${safePage}-${scope}`}>
          {listQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
          ) : listQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={
                listQuery.error instanceof Error
                  ? listQuery.error.message
                  : "Could not load the callback queue"
              }
              onRetry={() => listQuery.refetch()}
            />
          ) : pageRows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={PhoneOff}
                  title={query ? "No matching callbacks" : "Nothing in this queue"}
                  description={
                    query
                      ? "No callback matches that search in the current scope."
                      : "When the agent cannot reach an advisor it books a callback here."
                  }
                />
              </td>
            </tr>
          ) : (
            pageRows.map((row) => {
              const customer = callbackCustomer(row);
              const priority = priorityLabel(row.priority_level);
              return (
                <tr key={row.id} className="group">
                  <Td>
                    <div className="flex flex-col">
                      <span className="t-ui text-ink-1">{customer.name}</span>
                      <span className="t-mono-s text-ink-4">{customer.phone}</span>
                    </div>
                  </Td>
                  <Td>
                    <div className="flex items-center gap-sp-3">
                      <span className="t-mono-s text-ink-2">
                        {formatBusinessDayTime(row.scheduled_time, timeZone)}
                      </span>
                      {priority ? <Token strong>{priority}</Token> : null}
                    </div>
                  </Td>
                  <Td>
                    {row.preferred_window ? (
                      <Token>{row.preferred_window}</Token>
                    ) : (
                      <span className="t-caption text-ink-5">—</span>
                    )}
                  </Td>
                  <Td>
                    <span className="t-ui-regular text-ink-3">{row.reason ?? "—"}</span>
                  </Td>
                  <Td>
                    {row.assigned_advisor_name ? (
                      <div className="flex items-center gap-sp-4">
                        <Avatar size="sm" initials={initials(row.assigned_advisor_name)} />
                        <span className="t-ui text-ink-2">{row.assigned_advisor_name}</span>
                      </div>
                    ) : (
                      <span className="t-caption text-ink-5">Unassigned</span>
                    )}
                  </Td>
                  <Td>
                    {row.attempts > 0 ? (
                      <Token strong={row.attempts > 1}>{row.attempts}</Token>
                    ) : (
                      <span className="t-caption text-ink-5">—</span>
                    )}
                  </Td>
                  <Td>
                    <StatusChip status={callbackStatusKey(row)} />
                  </Td>
                  <Td>
                    <div className="flex items-center justify-end gap-sp-3 opacity-0 transition-opacity duration-[120ms] group-hover:opacity-100 focus-within:opacity-100">
                      <Button size="sm" variant="ghost" onClick={() => setDetailFor(row)}>
                        Detail
                      </Button>
                      {row.status === "pending" ? (
                        <>
                          <Button size="sm" variant="secondary" onClick={() => setOutcomeFor(row)}>
                            Outcome
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setCancelFor(row)}>
                            Cancel
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </Td>
                </tr>
              );
            })
          )}
        </TableBodySwap>
      </TableShell>

      {outcomeFor ? (
        <CallbackOutcomeModal
          callback={outcomeFor}
          timeZone={timeZone}
          onClose={() => setOutcomeFor(null)}
        />
      ) : null}
      {cancelFor ? (
        <CallbackCancelModal
          callback={cancelFor}
          timeZone={timeZone}
          onClose={() => setCancelFor(null)}
        />
      ) : null}
      <CallbackLifecycleModal
        callback={detailFor}
        timeZone={timeZone}
        onClose={() => setDetailFor(null)}
      />
    </PageSection>
  );
}
