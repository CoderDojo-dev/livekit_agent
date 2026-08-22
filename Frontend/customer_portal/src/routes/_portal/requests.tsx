import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { brand, copy, pageTitle } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchRequests, type RequestItem } from "@/lib/api/requests.server";
import { REQUEST_TONE, isActiveRequest } from "@/lib/request-status";
import { dateTime } from "@/lib/format";
import {
  CircleHelp,
  Gavel,
  Inbox,
  ReceiptText,
  Search,
  Signal,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import {
  Button,
  Card,
  Divider,
  IconFrame,
  SearchField,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import {
  AnimatedTabs,
  DataSection,
  InteractiveRow,
  PageSection,
  Pagination,
  Panel,
  RowChevron,
} from "@/components/portal/data";

export const Route = createFileRoute("/_portal/requests")({
  head: () => ({
    meta: [
      { title: pageTitle("Requests") },
      {
        name: "description",
        content:
          "Track everything we are working on for you, from the moment a request is received to the day it is resolved.",
      },
      { property: "og:title", content: brand.name },
      {
        property: "og:description",
        content: "A plain timeline of what we are doing for you, and what needs your reply.",
      },
    ],
  }),
  component: RequestsScreen,
});

const PAGE_SIZE = 10;

const TABS = [
  { id: "active", label: copy.requests.tabs.active },
  { id: "resolved", label: copy.requests.tabs.resolved },
  { id: "all", label: copy.requests.tabs.all },
] as const;

function requestTitle(item: RequestItem): string {
  return item.subject ?? copy.labels.requestCategory[item.category] ?? item.category;
}

/* One glyph per ticketing.tickets.category. The keys are exactly the union the
 * API declares, so a category added upstream fails the build here rather than
 * rendering a row with a hole where the icon should be. */
const CATEGORY_ICON: Record<RequestItem["category"], LucideIcon> = {
  network_complaint: Signal,
  formal_complaint: Gavel,
  technical: Wrench,
  billing: ReceiptText,
  other: CircleHelp,
};

/** Priority reads by weight, never by hue (22.4). Urgent is the only one that
 *  gets the filled chip; the rest step down through the outline family. */
const PRIORITY_TONE: Record<string, "solid" | "outline" | "dashed" | "muted"> = {
  urgent: "solid",
  high: "outline",
  medium: "dashed",
  low: "muted",
};

function RequestsScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("active");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<RequestItem | null>(null);
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";
  const searching = query.trim() !== "";

  const heroQuery = useQuery({
    queryKey: qk.requests(cid, undefined, 10, 0),
    queryFn: () => fetchRequests({ data: { status: undefined, limit: 10, offset: 0 } }),
    staleTime: 30_000,
  });
  const requestsQuery = useQuery({
    queryKey: qk.requests(cid, undefined, 50, 0),
    queryFn: () => fetchRequests({ data: { status: undefined, limit: 50, offset: 0 } }),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  const hero = heroQuery.data?.items?.find((r) => isActiveRequest(r.status));

  const filtered = useMemo(() => {
    const all = requestsQuery.data?.items ?? [];
    const byTab =
      tab === "all"
        ? all
        : tab === "active"
          ? all.filter((r) => isActiveRequest(r.status))
          : all.filter((r) => !isActiveRequest(r.status));
    const trimmed = query.trim().toLowerCase();
    if (trimmed === "") return byTab;
    return byTab.filter((r) =>
      (r.reference + " " + r.subject + " " + r.category).toLowerCase().includes(trimmed),
    );
  }, [tab, query, requestsQuery.data]);

  const rows = useMemo(
    () => filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE),
    [filtered, page],
  );

  const state = {
    isPending: requestsQuery.isPending,
    isFetching: requestsQuery.isFetching,
    error: requestsQuery.error,
  };

  const empty = searching
    ? {
        title: copy.empty.filtered.title,
        body: copy.empty.filtered.body,
        icon: Search,
        action: (
          <Button
            variant="secondary"
            onClick={() => {
              setQuery("");
              setPage(0);
            }}
          >
            {copy.empty.filtered.action}
          </Button>
        ),
      }
    : {
        title: copy.requests.empty.title,
        body: copy.requests.empty.body,
        icon: Inbox,
        action: (
          <Button
            variant="secondary"
            onClick={() => {
              setTab("all");
              setPage(0);
            }}
          >
            {copy.requests.empty.action}
          </Button>
        ),
      };

  return (
    <div className="space-y-sp-9">
      {hero ? (
        <PageSection
          index={0}
          label={copy.requests.heroLabel}
          right={
            <StatusChip tone={REQUEST_TONE[hero.status]} live>
              {copy.labels.requestStatus[hero.status] ?? hero.status}
            </StatusChip>
          }
        >
          <Card>
            <div className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
              <div className="flex min-w-0 items-start gap-sp-6">
                <IconFrame
                  icon={CATEGORY_ICON[hero.category] ?? CircleHelp}
                  size="lg"
                  tone="strong"
                />
                <div className="min-w-0">
                  <div className="t-title-2 truncate text-ink-1">{requestTitle(hero)}</div>
                  {/* Reference, opened-at and priority on one wrapped row. The
                      first two were already here; priority was in the payload
                      and only visible after opening the panel, which is the
                      wrong side of the click for the one field that says how
                      urgent this is. */}
                  <div className="mt-sp-4 flex flex-wrap items-center gap-sp-5">
                    <span className="t-mono-s text-ink-5">{hero.reference}</span>
                    <span className="t-mono-s text-ink-5">{dateTime(hero.created_at)}</span>
                    <StatusChip tone="muted">
                      {copy.labels.requestCategory[hero.category] ?? hero.category}
                    </StatusChip>
                    {hero.priority ? (
                      <StatusChip tone={PRIORITY_TONE[hero.priority] ?? "muted"}>
                        {copy.labels.priority[hero.priority] ?? hero.priority}
                      </StatusChip>
                    ) : null}
                  </div>
                </div>
              </div>
              <Button variant="primary" onClick={() => setSelected(hero)} className="shrink-0">
                {copy.requests.open}
              </Button>
            </div>
          </Card>
        </PageSection>
      ) : null}

      <div className="flex flex-wrap items-center gap-sp-5">
        <AnimatedTabs
          tabs={TABS.map((t) => ({
            id: t.id,
            label: t.label,
            count: (requestsQuery.data?.items ?? []).filter((r) =>
              t.id === "all"
                ? true
                : t.id === "active"
                  ? isActiveRequest(r.status)
                  : !isActiveRequest(r.status),
            ).length,
          }))}
          value={tab}
          onChange={(next) => {
            setTab(next);
            setPage(0);
          }}
        />
        <SearchField
          placeholder={copy.requests.search}
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(0);
          }}
          className="max-w-xs"
        />
      </div>

      <DataSection
        index={1}
        state={state}
        items={rows}
        skeletonRows={5}
        empty={empty}
        onRetry={() => void requestsQuery.refetch()}
      >
        {(items) => (
          <>
            <ul className="divide-y divide-stroke-subtle">
              {items.map((r) => (
                <li key={r.reference}>
                  {/* The row was four cells in a straight line: reference,
                      date, subject, status — three of them monospaced greys
                      competing with the one line that says what the request
                      is. The subject now leads, the two identifiers drop to a
                      caption beneath it, and the category becomes a glyph. */}
                  <InteractiveRow
                    onClick={() => setSelected(r)}
                    className="flex items-center gap-sp-5"
                  >
                    <IconFrame icon={CATEGORY_ICON[r.category] ?? CircleHelp} />
                    <span className="min-w-0 flex-1">
                      <span className="t-body-strong block truncate text-ink-1">
                        {requestTitle(r)}
                      </span>
                      <span className="t-mono-s mt-sp-1 flex flex-wrap items-center gap-sp-4 text-ink-5">
                        <span>{r.reference}</span>
                        <span aria-hidden="true">·</span>
                        <span>{dateTime(r.created_at)}</span>
                      </span>
                    </span>
                    <StatusChip tone={REQUEST_TONE[r.status]}>
                      {copy.labels.requestStatus[r.status] ?? r.status}
                    </StatusChip>
                    <RowChevron />
                  </InteractiveRow>
                </li>
              ))}
            </ul>
            <Pagination
              total={filtered.length}
              limit={PAGE_SIZE}
              offset={page * PAGE_SIZE}
              onOffsetChange={(next) => setPage(Math.floor(next / PAGE_SIZE))}
              busy={state.isFetching}
            />
          </>
        )}
      </DataSection>

      <Panel
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected?.reference ?? ""}
      >
        {selected ? (
          <>
            <SectionLabel
              right={
                <StatusChip tone={REQUEST_TONE[selected.status]}>
                  {copy.labels.requestStatus[selected.status] ?? selected.status}
                </StatusChip>
              }
            >
              {requestTitle(selected)}
            </SectionLabel>
            <Divider className="mt-sp-7" />
            {/* The em dash here was mojibake: the literal had been round-tripped
                through the wrong encoding, so a request with no priority
                printed three Latin-1 characters into the panel instead of one
                dash. copy.common.notApplicable is the one place in the portal
                that glyph is allowed to live. */}
            <dl className="mt-sp-7 grid grid-cols-2 gap-sp-5">
              {[
                [
                  copy.requests.category,
                  copy.labels.requestCategory[selected.category] ?? selected.category,
                ],
                [
                  copy.requests.priority,
                  selected.priority
                    ? (copy.labels.priority[selected.priority] ?? selected.priority)
                    : copy.common.notApplicable,
                ],
                [copy.requests.created, dateTime(selected.created_at)],
                [copy.requests.updated, dateTime(selected.updated_at)],
              ].map(([k, v]) => (
                <div
                  key={k}
                  className="rounded-r-2 border border-stroke-subtle bg-surface-2 p-sp-5"
                >
                  <dt className="t-micro-2 text-ink-5">{k}</dt>
                  <dd className="t-body-strong mt-sp-2 text-ink-1">{v}</dd>
                </div>
              ))}
            </dl>
            <Divider className="my-sp-7" />
            <div className="t-micro text-ink-4">{copy.requests.timeline}</div>
            {/* Two loose bullets became a rail: a hairline runs down the
                gutter and each step hangs a marker off it, so "received, then
                this" reads as one sequence rather than two unrelated lines.
                The current step is the filled marker. */}
            <ol className="relative mt-sp-6 space-y-sp-7 ps-sp-7">
              <span
                aria-hidden="true"
                className="absolute inset-y-sp-2 start-[3px] w-px bg-stroke-subtle"
              />
              <li className="relative">
                <span
                  aria-hidden="true"
                  className="absolute -start-sp-7 top-sp-2 h-[7px] w-[7px] rounded-r-1 border border-stroke-strong bg-surface-1"
                />
                <div className="t-ui text-ink-2">{copy.labels.requestStatus.open}</div>
                <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(selected.created_at)}</div>
              </li>
              {selected.updated_at ? (
                <li className="relative">
                  <span
                    aria-hidden="true"
                    className="absolute -start-sp-7 top-sp-2 h-[7px] w-[7px] rounded-r-1 bg-n-11"
                  />
                  <div className="t-ui text-ink-1">
                    {copy.labels.requestStatus[selected.status] ?? selected.status}
                  </div>
                  <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(selected.updated_at)}</div>
                </li>
              ) : null}
            </ol>
          </>
        ) : null}
      </Panel>
    </div>
  );
}
