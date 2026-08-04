import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { PhoneOff } from "lucide-react";
import { z } from "zod";
import {
  Avatar,
  Button,
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { Transcript } from "@/components/nexus/transcript";
import { getCoverage } from "@/lib/api/availability.server";
import { getSessionDetail, listSessions } from "@/lib/api/sessions.server";
import {
  callTime,
  callerName,
  dispositionKey,
  durationLabel,
  frustrationLabel,
} from "@/lib/nexus/call-view";
import { availabilityKeys, callKeys } from "@/lib/nexus/query-keys";
import { initials, maskPhone } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

const SCOPES = [
  { id: "", label: "All" },
  { id: "resolved", label: "Resolved" },
  { id: "escalated", label: "Escalated" },
  { id: "dropped", label: "Dropped" },
  { id: "abandoned", label: "Abandoned" },
];

export const Route = createFileRoute("/calls")({
  // F12 — deep-linkable selection. Does NOT alter routeTree.gen.ts.
  // .catch({}) swallows a malformed ?session (e.g. /calls?session=abc) so the SSR renderer
  // never throws: an invalid value is treated exactly like "no selection", never a crash.
  validateSearch: z
    .object({ session: z.string().uuid().optional() })
    .catch({ session: undefined }),
  head: () => ({
    meta: [
      { title: "Call History & Transcripts — Nexus" },
      {
        name: "description",
        content: "End-of-call records, sentiment timelines and full transcripts for every session.",
      },
      { property: "og:title", content: "Call History & Transcripts — Nexus" },
      { property: "og:description", content: "Transcripts and outcomes for customer calls." },
    ],
  }),
  component: CallsPage,
});

function CallsPage() {
  const navigate = useNavigate({ from: "/calls" });
  const { session: selected } = Route.useSearch();

  const [search, setSearch] = useState("");
  const [disposition, setDisposition] = useState("");
  const [limit, setLimit] = useState(50);

  const listQuery = useQuery({
    queryKey: callKeys.list(search, disposition, limit),
    queryFn: () =>
      listSessions({
        data: {
          limit,
          offset: 0,
          disposition: disposition || undefined,
          search: search || undefined,
        },
      }),
  });

  // F3 — business timezone; shared cache with /availability and /callbacks.
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const detailQuery = useQuery({
    queryKey: callKeys.detail(selected ?? ""),
    queryFn: () => getSessionDetail({ data: { sessionId: selected! } }),
    enabled: Boolean(selected),
  });

  const rows = listQuery.data?.sessions ?? [];
  const total = listQuery.data?.total ?? 0;
  const activeRow = rows.find((r) => r.session_id === selected) ?? null;

  const select = (sessionId: string) => navigate({ search: { session: sessionId }, replace: true });

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[340px_1fr]">
      {/* ---------------- Master list ---------------- */}
      <Card padded={false} className="overflow-hidden">
        <div className="space-y-sp-5 border-b border-stroke-subtle p-sp-6">
          <SearchInput placeholder="Search by number" value={search} onChange={setSearch} />
          <Segmented
            items={SCOPES.map((s) => s.label)}
            active={SCOPES.find((s) => s.id === disposition)!.label}
            onSelect={(label) => setDisposition(SCOPES.find((s) => s.label === label)!.id)}
          />
        </div>

        {listQuery.isPending ? (
          <div className="space-y-sp-4 p-sp-6">
            <span
              aria-hidden="true"
              className="block h-[52px] animate-pulse rounded-r-1 bg-surface-4"
            />
            <span
              aria-hidden="true"
              className="block h-[52px] animate-pulse rounded-r-1 bg-surface-4"
            />
            <span
              aria-hidden="true"
              className="block h-[52px] animate-pulse rounded-r-1 bg-surface-4"
            />
          </div>
        ) : listQuery.isError ? (
          <div className="p-sp-6">
            <ErrorState error={listQuery.error} onRetry={() => listQuery.refetch()} />
          </div>
        ) : rows.length === 0 ? (
          <div className="p-sp-6">
            <EmptyState
              icon={PhoneOff}
              title="No calls found"
              description="No session matches this filter yet."
            />
          </div>
        ) : (
          <>
            <ul className="max-h-[720px] overflow-y-auto">
              {rows.map((row) => {
                const active = row.session_id === selected;
                const name = callerName(row);
                return (
                  <li key={row.session_id}>
                    <button
                      type="button"
                      onClick={() => select(row.session_id)}
                      className={cn(
                        "flex w-full items-start gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5 text-left transition-colors duration-[120ms]",
                        active ? "bg-surface-3" : "hover:bg-surface-3/60",
                      )}
                    >
                      <Avatar initials={initials(name)} name={name} />
                      <span className="min-w-0 flex-1">
                        <span className="t-ui block truncate text-ink-1">{name}</span>
                        <span className="t-mono-s block truncate text-ink-4">
                          {row.msisdn ? maskPhone(row.msisdn) : "No number"}
                        </span>
                      </span>
                      <span className="text-right">
                        <span className="t-mono-s block text-ink-3">
                          {durationLabel(row.duration_seconds)}
                        </span>
                        <span className="t-caption block text-ink-5">
                          {callTime(row.start_time, timeZone)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="flex items-center justify-between gap-sp-4 border-t border-stroke-subtle px-sp-6 py-sp-5">
              <span className="t-caption text-ink-5">
                Showing {rows.length} of {total}
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </div>
          </>
        )}
      </Card>

      {/* ---------------- Detail ---------------- */}
      <div className="space-y-sp-6">
        {!selected ? (
          <Card>
            <EmptyState
              icon={PhoneOff}
              title="Select a call"
              description="Pick a session on the left to read its transcript."
            />
          </Card>
        ) : (
          <>
            <Card>
              <div className="flex flex-wrap items-start gap-sp-6">
                <Avatar
                  initials={initials(activeRow ? callerName(activeRow) : "?")}
                  name={activeRow ? callerName(activeRow) : "Call record"}
                  size="xl"
                />
                <div className="min-w-0">
                  <h2 className="t-title-2 text-ink-1">
                    {activeRow ? callerName(activeRow) : "Call record"}
                  </h2>
                  <p className="t-mono-s mt-sp-2 text-ink-4">
                    {selected.slice(0, 8)}
                    {activeRow?.msisdn ? ` \u00b7 ${maskPhone(activeRow.msisdn)}` : ""}
                  </p>
                  <div className="mt-sp-5 flex flex-wrap items-center gap-sp-4">
                    <StatusChip
                      status={dispositionKey(
                        detailQuery.data?.disposition ?? activeRow?.disposition ?? null,
                      )}
                    />
                    <Token>
                      {durationLabel(
                        detailQuery.data?.duration_seconds ?? activeRow?.duration_seconds ?? null,
                      )}
                    </Token>
                    {activeRow ? <Token>{callTime(activeRow.start_time, timeZone)}</Token> : null}
                    {activeRow?.customer_vip ? <Token strong>VIP</Token> : null}
                    {activeRow?.channel && activeRow.channel !== "voice" ? (
                      <Token mono={false}>{activeRow.channel}</Token>
                    ) : null}
                  </div>
                </div>
                <div className="ml-auto text-right">
                  <span className="t-micro block text-ink-5">Peak frustration</span>
                  <span className="t-metric-m block text-ink-1">
                    {frustrationLabel(detailQuery.data?.max_frustration ?? null)}
                  </span>
                </div>
              </div>

              {!timeZone && !coverageQuery.isPending ? (
                <p className="t-caption mt-sp-5 text-ink-5">
                  Times shown in UTC — the business timezone could not be loaded.
                </p>
              ) : null}
            </Card>

            <Card padded={false}>
              <div className="flex items-center justify-between gap-sp-5 p-sp-7">
                <CardHeader
                  title="Transcript"
                  subtitle="Speaker-attributed and PII-masked at capture."
                />
                {detailQuery.data ? (
                  <span className="t-caption text-ink-5">
                    {detailQuery.data.turns.length} turns
                  </span>
                ) : null}
              </div>

              {detailQuery.isPending ? (
                <div className="p-sp-7">
                  <CardSkeleton />
                </div>
              ) : detailQuery.isError ? (
                <div className="p-sp-7">
                  {/* F2 — a NULL frustration score makes the backend 500. Stay honest, stay usable. */}
                  <ErrorState error={detailQuery.error} onRetry={() => detailQuery.refetch()} />
                </div>
              ) : detailQuery.data && detailQuery.data.turns.length === 0 ? (
                <div className="p-sp-7">
                  <EmptyState
                    icon={PhoneOff}
                    title="No transcript"
                    description="This session ended before any turn was recorded."
                  />
                </div>
              ) : detailQuery.data ? (
                <Transcript turns={detailQuery.data.turns} sentiment={detailQuery.data.sentiment} />
              ) : null}
            </Card>
          </>
        )}
      </div>
    </PageSection>
  );
}
