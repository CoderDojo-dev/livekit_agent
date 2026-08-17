import { useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AudioLines, Inbox, PhoneCall } from "lucide-react";
import { copy, personaLabel } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import {
  fetchCallbacks,
  fetchConversation,
  fetchConversations,
  type CallbackItem,
  type ConversationSummary,
} from "@/lib/api/activity.server";
import { fetchRequests, type RequestItem } from "@/lib/api/requests.server";
import { REQUEST_TONE } from "@/lib/request-status";
import { dateTime, duration, relative } from "@/lib/format";
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
  ErrorState,
  InteractiveRow,
  MetricTile,
  PageSection,
  Pagination,
  Panel,
  SkeletonList,
  SkeletonMetric,
} from "@/components/portal/data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/activity")({
  head: () => ({
    meta: [
      { title: "Activity — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Every conversation, request, and callback between you and the Nexus assistant, with transcripts and what changed.",
      },
      { property: "og:title", content: "Activity — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Revisit any conversation and see exactly what the assistant did.",
      },
    ],
  }),
  component: ActivityScreen,
});

const PAGE_SIZE = 10;
const FULL_LIMIT = 50;

const TABS = [
  { id: "all", label: copy.activity.tabs.all },
  { id: "conversation", label: copy.activity.tabs.conversations },
  { id: "request", label: copy.activity.tabs.requests },
  { id: "callback", label: copy.activity.tabs.callbacks },
] as const;

const KIND_ICON = {
  conversation: AudioLines,
  request: Inbox,
  callback: PhoneCall,
} as const;

const CALLBACK_TONE: Record<CallbackItem["status"], "solid" | "outline" | "dashed" | "muted"> = {
  pending: "dashed",
  completed: "outline",
  cancelled: "muted",
};

type ListItem = {
  kind: "conversation" | "request" | "callback";
  id: string;
  title: string;
  caption: string;
  at: string | null;
  conversation?: ConversationSummary;
  request?: RequestItem;
  callback?: CallbackItem;
};

type Selection =
  | { kind: "conversation"; sessionId: string }
  | { kind: "request"; item: RequestItem }
  | { kind: "callback"; item: CallbackItem };

function requestTitle(item: RequestItem): string {
  return item.subject ?? copy.labels.requestCategory[item.category] ?? item.category;
}

function requestCaption(item: RequestItem): string {
  return copy.labels.requestCategory[item.category] ?? item.category;
}

function toItems(
  conversations: ConversationSummary[],
  requests: RequestItem[],
  callbacks: CallbackItem[],
): ListItem[] {
  const rows: ListItem[] = [
    ...conversations.map((c) => ({
      kind: "conversation" as const,
      id: c.session_id,
      title: copy.labels.channel[c.channel as keyof typeof copy.labels.channel] ?? c.channel,
      caption: c.disposition
        ? (copy.labels.disposition[c.disposition as keyof typeof copy.labels.disposition] ??
          c.disposition)
        : `${c.turns} ${copy.activity.turns}`,
      at: c.started_at,
      conversation: c,
    })),
    ...requests.map((r) => ({
      kind: "request" as const,
      id: r.reference,
      title: requestTitle(r),
      caption: requestCaption(r),
      at: r.created_at,
      request: r,
    })),
    ...callbacks.map((cb, i) => ({
      kind: "callback" as const,
      id: cb.scheduled_time ?? `${cb.reason ?? "callback"}-${i}`,
      title:
        copy.labels.callbackStatus[cb.status as keyof typeof copy.labels.callbackStatus] ??
        cb.status,
      caption: cb.reason ?? "—",
      at: cb.scheduled_time,
      callback: cb,
    })),
  ];
  return rows.sort((a, b) => {
    const ta = a.at ? new Date(a.at).getTime() : -Infinity;
    const tb = b.at ? new Date(b.at).getTime() : -Infinity;
    return tb - ta;
  });
}

function selectionFor(item: ListItem): Selection {
  if (item.conversation) return { kind: "conversation", sessionId: item.conversation.session_id };
  if (item.request) return { kind: "request", item: item.request };
  return { kind: "callback", item: item.callback! };
}

function ConversationBody({ sessionId }: { sessionId: string }) {
  const session = usePortalSession();
  const query = useQuery({
    queryKey: qk.conversation(session?.customerId ?? "unknown", sessionId),
    queryFn: () => fetchConversation({ data: { sessionId } }),
    staleTime: 30_000,
  });

  if (query.isPending) {
    return <SkeletonList rows={4} />;
  }

  if (query.isError || !query.data) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const detail = query.data;

  return (
    <>
      <SectionLabel
        right={
          detail.disposition ? (
            <StatusChip tone="outline">
              {copy.labels.disposition[
                detail.disposition as keyof typeof copy.labels.disposition
              ] ?? detail.disposition}
            </StatusChip>
          ) : null
        }
      >
        {copy.labels.channel[detail.channel as keyof typeof copy.labels.channel] ?? detail.channel}
      </SectionLabel>
      <dl className="mt-sp-6 grid grid-cols-3 gap-sp-5">
        {[
          [copy.activity.when, dateTime(detail.started_at)],
          [copy.activity.duration, duration(detail.duration_seconds)],
          [copy.activity.turns, String(detail.turns)],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="t-micro-2 text-ink-5">{k}</dt>
            <dd className="t-mono mt-sp-2 text-ink-2">{v}</dd>
          </div>
        ))}
      </dl>

      {detail.turns.length > 0 && (
        <>
          <Divider className="my-sp-7" />
          <div className="t-micro text-ink-4">{copy.activity.transcript}</div>
          <div className="mt-sp-6 space-y-sp-6">
            {detail.turns.map((line, turnIndex) => {
              // Persona label from the persisted active_agent; a raw
              // identifier must never reach the screen.
              const persona = personaLabel(line.agent);
              const isAgentTurn = line.speaker === "agent";
              const previousAgent = detail.turns
                .slice(0, turnIndex)
                .reverse()
                .find((t) => t.speaker === "agent");
              const previousPersona = previousAgent ? personaLabel(previousAgent.agent) : undefined;
              // A one-line divider replaces repeating the persona on every
              // bubble when it changes between consecutive agent turns.
              const showDivider = isAgentTurn && !!previousAgent && previousPersona !== persona;
              return (
                <div key={line.index}>
                  {showDivider ? (
                    <div className="mb-sp-6 flex items-center gap-sp-4" aria-hidden="true">
                      <span className="t-micro-2 text-ink-5">
                        {copy.assistant.tools.nowWith(persona)}
                      </span>
                      <span className="h-px flex-1 bg-stroke-subtle" />
                    </div>
                  ) : null}
                  <div className="t-micro-2 mb-sp-2 flex gap-sp-4 text-ink-5">
                    <span>{copy.labels.speaker[line.speaker] ?? line.speaker}</span>
                    <span className="t-mono-s">{dateTime(line.at)}</span>
                  </div>
                  <p
                    className={cn(
                      "t-body",
                      line.speaker === "caller" ? "text-ink-3" : "text-ink-1",
                    )}
                  >
                    {line.text ?? "—"}
                  </p>
                </div>
              );
            })}
          </div>
        </>
      )}
    </>
  );
}

function RequestBody({ item }: { item: RequestItem }) {
  return (
    <>
      <SectionLabel
        right={
          <StatusChip tone={REQUEST_TONE[item.status]}>
            {copy.labels.requestStatus[item.status] ?? item.status}
          </StatusChip>
        }
      >
        <span className="t-mono">{item.reference}</span>
      </SectionLabel>
      <h3 className="t-title-2 mt-sp-6 text-ink-1">{requestTitle(item)}</h3>
      <Divider className="my-sp-7" />
      <dl className="grid grid-cols-2 gap-sp-5">
        {[
          [copy.requests.category, requestCaption(item)],
          [
            copy.requests.priority,
            item.priority ? (copy.labels.priority[item.priority] ?? item.priority) : "—",
          ],
          [copy.requests.created, dateTime(item.created_at)],
          [copy.requests.updated, dateTime(item.updated_at)],
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
            <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(item.created_at)}</div>
          </div>
        </li>
        {item.updated_at ? (
          <li className="flex items-baseline gap-sp-5">
            <span className="h-2 w-2 shrink-0 translate-y-[-2px] rounded-full bg-n-11" />
            <div className="min-w-0">
              <div className="t-ui text-ink-2">
                {copy.labels.requestStatus[item.status] ?? item.status}
              </div>
              <div className="t-mono-s mt-sp-1 text-ink-5">{dateTime(item.updated_at)}</div>
            </div>
          </li>
        ) : null}
      </ol>
    </>
  );
}

function CallbackBody({ item }: { item: CallbackItem }) {
  const status = item.status as "pending" | "completed" | "cancelled";
  return (
    <>
      <SectionLabel
        right={
          <StatusChip tone={CALLBACK_TONE[status] ?? "muted"}>
            {copy.labels.callbackStatus[status] ?? item.status}
          </StatusChip>
        }
      >
        {copy.activity.tabs.callbacks}
      </SectionLabel>
      <Divider className="mt-sp-7" />
      <dl className="mt-sp-7 grid grid-cols-2 gap-sp-5">
        {[
          [copy.activity.callbackTime, dateTime(item.scheduled_time)],
          [copy.activity.callbackWindow, item.preferred_window ?? "—"],
          [copy.requests.category, item.reason ?? "—"],
        ].map(([k, v]) => (
          <div key={k}>
            <dt className="t-micro-2 text-ink-5">{k}</dt>
            <dd className="t-body-strong mt-sp-2 text-ink-2">{v}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function ActivityScreen() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Selection | null>(null);
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";
  const searching = query.trim() !== "";
  const pagedKind = tab === "conversation" || tab === "request";
  const limit = pagedKind ? PAGE_SIZE : FULL_LIMIT;
  const offset = pagedKind ? page * PAGE_SIZE : 0;

  const heroQuery = useQuery({
    queryKey: qk.conversations(cid, 1, 0),
    queryFn: () => fetchConversations({ data: { limit: 1, offset: 0 } }),
    staleTime: 30_000,
  });
  const conversationsQuery = useQuery({
    queryKey: qk.conversations(cid, limit, offset),
    queryFn: () => fetchConversations({ data: { limit, offset } }),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const requestsQuery = useQuery({
    queryKey: qk.requests(cid, undefined, limit, offset),
    queryFn: () => fetchRequests({ data: { status: undefined, limit, offset } }),
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });
  const callbacksQuery = useQuery({
    queryKey: qk.callbacks(cid, 20, 0),
    queryFn: () => fetchCallbacks({ data: { limit: 20, offset: 0 } }),
    staleTime: 30_000,
  });

  const hero = heroQuery.data?.items?.[0];

  const byTab = useMemo(() => {
    const rows = toItems(
      conversationsQuery.data?.items ?? [],
      requestsQuery.data?.items ?? [],
      callbacksQuery.data?.items ?? [],
    );
    return tab === "all" ? rows : rows.filter((r) => r.kind === tab);
  }, [tab, conversationsQuery.data, requestsQuery.data, callbacksQuery.data]);

  const searched = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (trimmed === "") return byTab;
    return byTab.filter((r) => (r.title + " " + r.caption).toLowerCase().includes(trimmed));
  }, [byTab, query]);

  const rows = useMemo(() => {
    const start = page * PAGE_SIZE;
    return searched.slice(start, start + PAGE_SIZE);
  }, [searched, page]);

  const counts: Record<(typeof TABS)[number]["id"], number> = {
    all:
      (conversationsQuery.data?.total ?? 0) +
      (requestsQuery.data?.total ?? 0) +
      (callbacksQuery.data?.items.length ?? 0),
    conversation: conversationsQuery.data?.total ?? 0,
    request: requestsQuery.data?.total ?? 0,
    callback: callbacksQuery.data?.items.length ?? 0,
  };

  const paginationTotal =
    tab === "conversation"
      ? searching
        ? searched.length
        : (conversationsQuery.data?.total ?? searched.length)
      : tab === "request"
        ? searching
          ? searched.length
          : (requestsQuery.data?.total ?? searched.length)
        : searched.length;

  const state = {
    isPending: conversationsQuery.isPending || requestsQuery.isPending || callbacksQuery.isPending,
    isFetching:
      conversationsQuery.isFetching || requestsQuery.isFetching || callbacksQuery.isFetching,
    error: conversationsQuery.error ?? requestsQuery.error ?? callbacksQuery.error,
  };

  const retry = () =>
    void Promise.allSettled([
      conversationsQuery.refetch(),
      requestsQuery.refetch(),
      callbacksQuery.refetch(),
    ]);

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
        title: copy.empty.activityA.title,
        body: copy.empty.activityA.body,
        action: (
          <Button variant="primary" onClick={() => void navigate({ to: "/assistant" })}>
            {copy.empty.activityA.action}
          </Button>
        ),
      };

  const panelTitle =
    selected?.kind === "request"
      ? selected.item.reference
      : selected?.kind === "callback"
        ? (copy.labels.callbackStatus[
            selected.item.status as keyof typeof copy.labels.callbackStatus
          ] ?? selected.item.status)
        : copy.activity.tabs.conversations;

  return (
    <div className="space-y-sp-9">
      {heroQuery.isPending ? (
        <PageSection label={copy.activity.heroLabel}>
          <Card>
            <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
              <SkeletonMetric />
              <SkeletonMetric />
              <SkeletonMetric />
            </div>
          </Card>
        </PageSection>
      ) : hero ? (
        <PageSection
          label={copy.activity.heroLabel}
          right={
            hero.disposition ? (
              <StatusChip tone="outline">
                {copy.labels.disposition[
                  hero.disposition as keyof typeof copy.labels.disposition
                ] ?? hero.disposition}
              </StatusChip>
            ) : undefined
          }
        >
          <Card>
            <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
              <MetricTile label={copy.activity.when} value={dateTime(hero.started_at)} />
              <MetricTile label={copy.activity.duration} value={duration(hero.duration_seconds)} />
              <MetricTile label={copy.activity.turns} value={String(hero.turns)} />
            </div>
            <div className="mt-sp-7">
              <Button
                variant="primary"
                onClick={() => setSelected({ kind: "conversation", sessionId: hero.session_id })}
              >
                {copy.activity.open}
              </Button>
            </div>
          </Card>
        </PageSection>
      ) : null}

      <div className="flex flex-wrap items-center gap-sp-5">
        <AnimatedTabs
          tabs={TABS.map((t) => ({ id: t.id, label: t.label, count: counts[t.id] }))}
          value={tab}
          onChange={(next) => {
            setTab(next);
            setPage(0);
          }}
        />
        <SearchField
          placeholder={copy.activity.search}
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(0);
          }}
          className="max-w-xs"
        />
      </div>

      <DataSection state={state} items={rows} skeletonRows={5} empty={empty} onRetry={retry}>
        {(items) => (
          <>
            <ul className="divide-y divide-stroke-subtle">
              {items.map((item) => {
                const Icon = KIND_ICON[item.kind];
                return (
                  <li key={`${item.kind}-${item.id}`}>
                    <InteractiveRow
                      onClick={() => setSelected(selectionFor(item))}
                      className="flex items-start gap-sp-6"
                    >
                      <span className="mt-sp-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                        <Icon size={16} strokeWidth={1.5} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="t-body-strong block truncate text-ink-1">
                          {item.title}
                        </span>
                        <span className="t-caption mt-sp-2 line-clamp-2 block text-ink-4">
                          {item.caption}
                        </span>
                      </span>
                      <span className="t-mono-s shrink-0 pt-sp-2 text-ink-5">
                        {relative(item.at)}
                      </span>
                    </InteractiveRow>
                  </li>
                );
              })}
            </ul>
            <Pagination
              total={paginationTotal}
              limit={PAGE_SIZE}
              offset={page * PAGE_SIZE}
              onOffsetChange={(next) => setPage(Math.floor(next / PAGE_SIZE))}
              busy={state.isFetching}
            />
          </>
        )}
      </DataSection>

      <Panel open={selected !== null} onClose={() => setSelected(null)} title={panelTitle}>
        {selected?.kind === "conversation" ? (
          <ConversationBody sessionId={selected.sessionId} />
        ) : selected?.kind === "request" ? (
          <RequestBody item={selected.item} />
        ) : selected ? (
          <CallbackBody item={selected.item} />
        ) : null}
      </Panel>
    </div>
  );
}
