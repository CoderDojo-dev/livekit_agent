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
  Button,
  Card,
  Divider,
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
          label={copy.requests.heroLabel}
          right={
            <StatusChip tone={REQUEST_TONE[hero.status]}>
              {copy.labels.requestStatus[hero.status] ?? hero.status}
            </StatusChip>
          }
        >
          <Card>
            <div className="flex flex-col gap-sp-7 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0">
                <div className="t-title-2 truncate text-ink-1">{requestTitle(hero)}</div>
                <div className="mt-sp-4 flex flex-wrap items-center gap-sp-6">
                  <span className="t-mono-s text-ink-5">{hero.reference}</span>
                  <span className="t-mono-s text-ink-5">{dateTime(hero.created_at)}</span>
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
                  <InteractiveRow
                    onClick={() => setSelected(r)}
                    className="flex items-center gap-sp-5"
                  >
                    <span className="t-mono-s min-w-0 shrink-0 text-ink-5">{r.reference}</span>
                    <span className="t-mono-s shrink-0 text-ink-5">{dateTime(r.created_at)}</span>
                    <span className="t-body-strong min-w-0 flex-1 truncate text-ink-1">
                      {requestTitle(r)}
                    </span>
                    <StatusChip tone={REQUEST_TONE[r.status]}>
                      {copy.labels.requestStatus[r.status] ?? r.status}
                    </StatusChip>
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
                    : "â€”",
                ],
                [copy.requests.created, dateTime(selected.created_at)],
                [copy.requests.updated, dateTime(selected.updated_at)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="t-micro-2 text-ink-5">{k}</dt>
                  <dd className="t-body-strong mt-sp-2 text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
            <Divider className="my-sp-7" />
            <div className="t-micro text-ink-4">{copy.requests.timeline}</div>
            <ol className="mt-sp-6 space-y-sp-6">
              <li className="flex items-baseline gap-sp-5">
                <span className="h-2 w-2 shrink-0 translate-y-[-2px] rounded-full bg-n-11" />
                <div className="min-w-0">
                  <div className="t-ui text-ink-2">{copy.labels.requestStatus.open}</div>
                  <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(selected.created_at)}</div>
                </div>
              </li>
              {selected.updated_at ? (
                <li className="flex items-baseline gap-sp-5">
                  <span className="h-2 w-2 shrink-0 translate-y-[-2px] rounded-full bg-n-11" />
                  <div className="min-w-0">
                    <div className="t-ui text-ink-2">
                      {copy.labels.requestStatus[selected.status] ?? selected.status}
                    </div>
                    <div className="t-mono-s mt-sp-1 text-ink-5">
                      {dateTime(selected.updated_at)}
                    </div>
                  </div>
                </li>
              ) : null}
            </ol>
          </>
        ) : null}
      </Panel>
    </div>
  );
}
