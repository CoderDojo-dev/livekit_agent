import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { PhoneOff } from "lucide-react";
import { z } from "zod";
import {
  Avatar,
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, ListSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { PageSwap } from "@/components/nexus/motion";
import { clampPage, offsetFor } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";
import { Transcript } from "@/components/nexus/transcript";
import { SessionVerdicts } from "@/components/nexus/session-verdicts";
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
import { initials, formatPhone } from "@/lib/nexus/format";
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
  validateSearch: z.object({ session: z.string().uuid().optional() }).catch({ session: undefined }),
  head: () => ({
    meta: [
      { title: pageTitle("Call History & Transcripts") },
      {
        name: "description",
        content: "End-of-call records, sentiment timelines and full transcripts for every session.",
      },
      { property: "og:title", content: pageTitle("Call History & Transcripts") },
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
  const [page, setPage] = useState(0);

  /**
   * The master list is now paged instead of scrolled.
   *
   * It used to render up to 200 rows inside a `max-h-[720px] overflow-y-auto` container — a
   * nested scroller sitting inside the page scroll, with no fade or shadow to mark it. A wheel
   * over the list moved the list; two pixels right, it moved the page. Paging gives the column a
   * fixed, predictable height and leaves exactly one scrollbar on the screen.
   */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.listItem,
    chrome: 420,
    min: 5,
    max: 10,
    fallback: 6,
  });

  const listQuery = useQuery({
    queryKey: callKeys.list(search, disposition, pageSize, offsetFor(page, pageSize)),
    queryFn: () =>
      listSessions({
        data: {
          limit: pageSize,
          offset: offsetFor(page, pageSize),
          disposition: disposition || undefined,
          search: search || undefined,
        },
      }),
    placeholderData: keepPreviousData,
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

  /* A narrower filter must not strand the reader on a page index that no longer exists. */
  useEffect(() => setPage(0), [search, disposition, pageSize]);
  const safePage = clampPage(page, total, pageSize);

  const select = (sessionId: string) => navigate({ search: { session: sessionId }, replace: true });

  /**
   * Open on the newest call.
   *
   * The list arrives newest-first, so rows[0] is the most recent session. Landing on an empty
   * "Select a call" panel made the page look inert — the transcript is the reason to be here, and
   * the most recent call is almost always the one being asked about.
   *
   * Guarded three ways so it never fights the user:
   *  - only when nothing is selected (a deep link via ?session= always wins);
   *  - only on the FIRST page, so paging forward does not yank the reader to a new transcript;
   *  - `replace: true` keeps it out of history, so Back still leaves the page.
   */
  useEffect(() => {
    if (selected !== undefined) return;
    if (safePage !== 0) return;
    const newest = rows[0];
    if (newest) select(newest.session_id);
    // `select` is stable for this route; re-running on rows identity is what we want.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, safePage, rows]);

  return (
    <>
      {/*
       * FIXED, EQUAL HEIGHT FOR BOTH COLUMNS.
       *
       * Both panels used to size to their content, so a short call collapsed the transcript card
       * to a sliver while the list beside it stayed tall, and a long call did the reverse. The
       * band now declares ONE height and both children fill it: the list scrolls its rows, the
       * transcript scrolls its turns, and the card outlines never move between calls.
       *
       * The height is expressed in viewport units so it adapts to the display without ever being
       * derived from the content inside it.
       */}
      <PageSection
        index={0}
        className="grid gap-sp-6 xl:h-[calc(100vh-190px)] xl:min-h-[520px] xl:grid-cols-[340px_1fr]"
      >
        {/* ---------------- Master list ---------------- */}
        <Card padded={false} className="flex min-h-0 flex-col overflow-hidden">
          <div className="space-y-sp-5 border-b border-stroke-subtle p-sp-6">
            <SearchInput placeholder="Search by number" value={search} onChange={setSearch} />
            <Segmented
              items={SCOPES.map((s) => s.label)}
              active={SCOPES.find((s) => s.id === disposition)!.label}
              onSelect={(label) => setDisposition(SCOPES.find((s) => s.label === label)!.id)}
            />
          </div>

          {listQuery.isPending ? (
            <ListSkeleton rows={pageSize} />
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
              {/* min-h-0 is what lets a flex child actually shrink and scroll; without it the
               * list forces the card taller than the band. */}
              <PageSwap
                pageKey={safePage}
                className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
              >
                <ul>
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
                              {row.msisdn ? formatPhone(row.msisdn) : "No number"}
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
              </PageSwap>

              <div className="mt-auto border-t border-stroke-subtle px-sp-6 py-sp-5">
                <Pager
                  page={safePage}
                  pageSize={pageSize}
                  total={total}
                  onPageChange={setPage}
                  noun="calls"
                  busy={listQuery.isFetching && !listQuery.isPending}
                />
              </div>
            </>
          )}
        </Card>

        {/* ---------------- Detail ---------------- */}
        <div className="flex min-h-0 flex-col gap-sp-6">
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
                      {activeRow?.msisdn ? ` \u00b7 ${formatPhone(activeRow.msisdn)}` : ""}
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

              <Card padded={false} className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex shrink-0 items-center justify-between gap-sp-5 p-sp-7">
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
                  <Transcript
                    turns={detailQuery.data.turns}
                    sentiment={detailQuery.data.sentiment}
                  />
                ) : null}
              </Card>
            </>
          )}
        </div>
      </PageSection>

      {/* Policy verdicts span the full width, below both columns.
       * Inside the right-hand column this panel made the transcript column taller still, which
       * stretched the master list opposite it. It is also a per-call record in its own right,
       * not a footnote to the transcript, so a band of its own reads correctly. */}
      {selected ? (
        <PageSection index={1}>
          <SessionVerdicts sessionId={selected} />
        </PageSection>
      ) : null}
    </>
  );
}
