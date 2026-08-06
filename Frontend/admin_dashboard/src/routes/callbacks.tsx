import { useMemo, useState } from "react";
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

const LIMITS = ["100", "250", "500"];

export const Route = createFileRoute("/callbacks")({
  head: () => ({
    meta: [{ title: "Callbacks — Nexus" }],
  }),
  component: CallbacksPage,
});

function CallbacksPage() {
  const [scope, setScope] = useState<CallbackScope>("pending");
  const [limit, setLimit] = useState(100);
  const [query, setQuery] = useState("");
  const [outcomeFor, setOutcomeFor] = useState<Callback | null>(null);
  const [cancelFor, setCancelFor] = useState<Callback | null>(null);
  const [detailFor, setDetailFor] = useState<Callback | null>(null);

  const { status, overdueOnly } = scopeQuery(scope);

  const listQuery = useQuery({
    queryKey: callbackKeys.list(status, overdueOnly, limit),
    queryFn: () => listCallbacks({ data: { status, overdueOnly, limit } }),
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
  const truncated = rows.length >= limit;

  return (
    <PageSection>
      <div className="mb-sp-6 flex flex-wrap items-baseline gap-sp-5">
        <span className="t-caption text-ink-4">
          {statsQuery.data
            ? `${statsQuery.data.pending} pending · ${statsQuery.data.overdue} overdue · ${statsQuery.data.completed} completed`
            : "Queue health loading…"}
        </span>
        <span className="t-caption text-ink-5">
          {zoneKnown
            ? `times in ${timeZone}`
            : "business timezone unavailable — times shown in UTC"}
        </span>
      </div>

      <TableShell
        toolbar={
          <div className="flex w-full items-center justify-between gap-sp-5">
            <div className="flex items-center gap-sp-5">
              <Segmented
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
            <Segmented
              items={LIMITS}
              active={String(limit)}
              onSelect={(v) => setLimit(Number(v))}
            />
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
          <>
            <span className="t-caption text-ink-4">
              {visible.length === rows.length
                ? `${rows.length} callback${rows.length === 1 ? "" : "s"}`
                : `${visible.length} of ${rows.length} callbacks`}
            </span>
            <span className="t-caption text-ink-5">
              {truncated
                ? total !== null
                  ? `Showing the first ${limit} of ${total} · raise the limit to see more`
                  : `Showing the first ${limit} · raise the limit to see more`
                : "Ordered by priority, then soonest first"}
            </span>
          </>
        }
      >
        {listQuery.isPending ? (
          <TableSkeleton columns={COLUMN_COUNT} rows={6} />
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
        ) : visible.length === 0 ? (
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
          visible.map((row) => {
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
