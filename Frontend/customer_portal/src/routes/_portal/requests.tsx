import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import { fetchRequests, type RequestItem } from "@/lib/api/requests.server";
import { errorMessage } from "@/lib/api/errors";
import { dateTime } from "@/lib/format";
import {
  Button,
  Card,
  Divider,
  EmptyState,
  SearchField,
  SectionLabel,
  StatusChip,
  Tabs,
} from "@/components/portal/primitives";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/requests")({
  head: () => ({
    meta: [
      { title: "Requests — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Track everything Nexus is working on for you, from the moment a request is received to the day it is resolved.",
      },
      { property: "og:title", content: "Requests — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "A plain timeline of what we are doing for you, and what needs your reply.",
      },
    ],
  }),
  component: RequestsScreen,
});

const TABS = [
  { id: "active", label: copy.requests.tabs.active },
  { id: "resolved", label: copy.requests.tabs.resolved },
  { id: "all", label: copy.requests.tabs.all },
] as const;

const TONE: Record<RequestItem["status"], "solid" | "outline" | "dashed" | "muted"> = {
  open: "dashed",
  in_progress: "solid",
  pending: "dashed",
  resolved: "outline",
  closed: "muted",
};

function isActive(status: RequestItem["status"]): boolean {
  return status === "open" || status === "in_progress" || status === "pending";
}

function RequestsScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("active");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const session = usePortalSession();

  const requestsQuery = useQuery({
    queryKey: qk.requests(session?.customerId ?? "unknown", undefined, 50, 0),
    queryFn: () => fetchRequests({ data: { status: undefined, limit: 50, offset: 0 } }),
    staleTime: 30_000,
  });

  const list = useMemo(() => {
    const all = requestsQuery.data?.items ?? [];
    const byTab =
      tab === "all"
        ? all
        : tab === "active"
          ? all.filter((r) => isActive(r.status))
          : all.filter((r) => !isActive(r.status));
    const trimmed = query.trim().toLowerCase();
    if (trimmed === "") return byTab;
    return byTab.filter((r) =>
      (r.reference + " " + r.subject + " " + r.category).toLowerCase().includes(trimmed),
    );
  }, [tab, query, requestsQuery.data]);

  const active = list.find((r) => r.reference === selected) ?? list[0];

  if (requestsQuery.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading your requests…</p>
      </Card>
    );
  }

  if (requestsQuery.isError || !requestsQuery.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(requestsQuery.error)}
        </p>
        <Button
          variant="secondary"
          className="mt-sp-6"
          onClick={() => void requestsQuery.refetch()}
        >
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  if (list.length === 0) {
    return (
      <EmptyState
        title={copy.empty.filtered.title}
        body={copy.empty.filtered.body}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              setQuery("");
              setTab("all");
            }}
          >
            {copy.empty.filtered.action}
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-sp-9">
      <div className="flex flex-wrap items-center gap-sp-5">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <SearchField
          placeholder={copy.requests.search}
          value={query}
          onChange={setQuery}
          className="max-w-xs"
        />
      </div>

      <div className="grid gap-sp-7 lg:grid-cols-[minmax(0,1fr)_440px]">
        <ul className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
          {list.map((r) => (
            <li key={r.reference} className="border-b border-stroke-subtle last:border-b-0">
              <button
                onClick={() => setSelected(r.reference)}
                className={cn(
                  "focus-ring w-full px-sp-7 py-sp-6 text-left transition-colors duration-200",
                  active?.reference === r.reference ? "bg-surface-3" : "hover:bg-surface-2",
                )}
              >
                <div className="flex items-center gap-sp-5">
                  <span className="t-mono-s text-ink-5">{r.reference}</span>
                  <StatusChip tone={TONE[r.status]}>
                    {copy.labels.requestStatus[r.status] ?? r.status}
                  </StatusChip>
                  <span className="t-mono-s ml-auto text-ink-5">{dateTime(r.created_at)}</span>
                </div>
                <div className="t-body-strong mt-sp-4 text-ink-1">
                  {r.subject ?? copy.labels.requestCategory[r.category] ?? r.category}
                </div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {copy.labels.requestCategory[r.category] ?? r.category}
                </div>
              </button>
            </li>
          ))}
        </ul>

        {active && (
          <Card className="lg:sticky lg:top-24 lg:self-start">
            <SectionLabel
              right={
                <StatusChip tone={TONE[active.status]}>
                  {copy.labels.requestStatus[active.status] ?? active.status}
                </StatusChip>
              }
            >
              <span className="t-mono">{active.reference}</span>
            </SectionLabel>
            <h3 className="t-title-2 mt-sp-6 text-ink-1">
              {active.subject ?? copy.labels.requestCategory[active.category] ?? active.category}
            </h3>

            <Divider className="my-sp-7" />
            <dl className="grid grid-cols-2 gap-sp-5">
              {[
                [
                  copy.requests.category,
                  copy.labels.requestCategory[active.category] ?? active.category,
                ],
                [
                  copy.requests.priority,
                  active.priority
                    ? (copy.labels.priority[active.priority] ?? active.priority)
                    : "—",
                ],
                [copy.requests.created, dateTime(active.created_at)],
                [copy.requests.updated, dateTime(active.updated_at)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="t-micro-2 text-ink-5">{k}</dt>
                  <dd className="t-body-strong mt-sp-2 text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}
      </div>
    </div>
  );
}
