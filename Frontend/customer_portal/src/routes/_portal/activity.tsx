import { useMemo, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { usePortalSession } from "@/lib/use-portal-session";
import { useQuery } from "@tanstack/react-query";
import { AudioLines, Inbox, PhoneCall } from "lucide-react";
import { copy } from "@/lib/copy";
import { qk } from "@/lib/query-keys";
import {
  fetchCallbacks,
  fetchConversation,
  fetchConversations,
  type CallbackItem,
  type ConversationSummary,
} from "@/lib/api/activity.server";
import { fetchRequests, type RequestItem } from "@/lib/api/requests.server";
import { errorMessage } from "@/lib/api/errors";
import { dateTime, duration, relative } from "@/lib/format";
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

const REQUEST_TONE: Record<RequestItem["status"], "solid" | "outline" | "dashed" | "muted"> = {
  open: "dashed",
  in_progress: "solid",
  pending: "dashed",
  resolved: "outline",
  closed: "muted",
};

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
      title: copy.labels.callbackStatus[cb.status] ?? cb.status,
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

function ConversationDetailPanel({ sessionId }: { sessionId: string }) {
  const session = usePortalSession();
  const query = useQuery({
    queryKey: qk.conversation(session?.customerId ?? "unknown", sessionId),
    queryFn: () => fetchConversation({ data: { sessionId } }),
    staleTime: 30_000,
  });

  if (query.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading transcript…</p>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(query.error)}
        </p>
        <Button variant="secondary" className="mt-sp-6" onClick={() => void query.refetch()}>
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  const detail = query.data;

  return (
    <Card className="lg:sticky lg:top-24 lg:self-start">
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
          ["WHEN", dateTime(detail.started_at)],
          ["LENGTH", duration(detail.duration_seconds)],
          ["TURNS", String(detail.turns)],
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
          <div className="mt-sp-6 max-h-72 space-y-sp-6 overflow-y-auto pr-sp-3">
            {detail.turns.map((line) => (
              <div key={line.index}>
                <div className="t-micro-2 mb-sp-2 flex gap-sp-4 text-ink-5">
                  <span>
                    {copy.labels.speaker[line.speaker] ?? line.speaker}
                    {line.agent ? ` · ${line.agent}` : ""}
                  </span>
                  <span className="t-mono-s">{dateTime(line.at)}</span>
                </div>
                <p
                  className={cn("t-body", line.speaker === "caller" ? "text-ink-3" : "text-ink-1")}
                >
                  {line.text ?? "—"}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-sp-7 flex gap-sp-4">
            <Button variant="secondary" size="sm">
              {copy.assistant.stream.copyTranscript}
            </Button>
            <Button variant="quiet" size="sm">
              {copy.assistant.stream.downloadTranscript}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

function RequestDetailPanel({ item }: { item: RequestItem }) {
  return (
    <Card className="lg:sticky lg:top-24 lg:self-start">
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
    </Card>
  );
}

function CallbackDetailPanel({ item }: { item: CallbackItem }) {
  return (
    <Card className="lg:sticky lg:top-24 lg:self-start">
      <SectionLabel
        right={
          <StatusChip tone={CALLBACK_TONE[item.status]}>
            {copy.labels.callbackStatus[item.status] ?? item.status}
          </StatusChip>
        }
      >
        {copy.activity.tabs.callbacks}
      </SectionLabel>
      <h3 className="t-title-2 mt-sp-6 text-ink-1">
        {copy.labels.callbackStatus[item.status] ?? item.status}
      </h3>
      <Divider className="my-sp-7" />
      <dl className="grid grid-cols-2 gap-sp-5">
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
    </Card>
  );
}

function ActivityScreen() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";

  const conversationsQuery = useQuery({
    queryKey: qk.conversations(cid, 50, 0),
    queryFn: () => fetchConversations({ data: { limit: 50, offset: 0 } }),
    staleTime: 30_000,
  });
  const requestsQuery = useQuery({
    queryKey: qk.requests(cid, undefined, 50, 0),
    queryFn: () => fetchRequests({ data: { status: undefined, limit: 50, offset: 0 } }),
    staleTime: 30_000,
  });
  const callbacksQuery = useQuery({
    queryKey: qk.callbacks(cid),
    queryFn: () => fetchCallbacks(),
    staleTime: 30_000,
  });

  const list = useMemo(() => {
    const rows = toItems(
      conversationsQuery.data?.items ?? [],
      requestsQuery.data?.items ?? [],
      callbacksQuery.data?.items ?? [],
    );
    const byTab = tab === "all" ? rows : rows.filter((r) => r.kind === tab);
    const trimmed = query.trim().toLowerCase();
    if (trimmed === "") return byTab;
    return byTab.filter((r) => (r.title + " " + r.caption).toLowerCase().includes(trimmed));
  }, [tab, query, conversationsQuery.data, requestsQuery.data, callbacksQuery.data]);

  const hero = conversationsQuery.data?.items?.[0];
  const active = list.find((i) => i.id === selected) ?? list[0];

  if (conversationsQuery.isPending || requestsQuery.isPending || callbacksQuery.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading your activity…</p>
      </Card>
    );
  }

  if (
    hero === undefined &&
    (requestsQuery.data?.items.length ?? 0) === 0 &&
    (callbacksQuery.data?.items.length ?? 0) === 0
  ) {
    return (
      <EmptyState
        title={copy.empty.activityA.title}
        body={copy.empty.activityA.body}
        action={
          <Button variant="primary" onClick={() => void navigate({ to: "/assistant" })}>
            {copy.empty.activityA.action}
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-sp-9">
      {hero && (
        <Card className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="t-micro text-ink-5">{copy.activity.heroLabel}</div>
            <h2 className="t-title-1 mt-sp-4 truncate text-ink-1">
              {copy.labels.channel[hero.channel as keyof typeof copy.labels.channel] ??
                hero.channel}
            </h2>
            <div className="t-mono-s mt-sp-6 flex flex-wrap items-center gap-sp-6 text-ink-5">
              <span>{dateTime(hero.started_at)}</span>
              <span>
                {duration(hero.duration_seconds)} {copy.activity.duration}
              </span>
              <span>
                {hero.turns} {copy.activity.turns}
              </span>
              {hero.disposition && (
                <StatusChip tone="outline">
                  {copy.labels.disposition[
                    hero.disposition as keyof typeof copy.labels.disposition
                  ] ?? hero.disposition}
                </StatusChip>
              )}
            </div>
          </div>
          <Button
            variant="primary"
            onClick={() => {
              setSelected(hero.session_id);
              setTab("conversation");
            }}
          >
            {copy.activity.open}
          </Button>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-sp-5">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <SearchField
          placeholder={copy.activity.search}
          value={query}
          onChange={setQuery}
          className="max-w-xs"
        />
      </div>

      {list.length === 0 ? (
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
      ) : (
        <div className="grid gap-sp-7 lg:grid-cols-[minmax(0,1fr)_420px]">
          <ul className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
            {list.map((item) => {
              const Icon = KIND_ICON[item.kind];
              const on = active?.id === item.id;
              return (
                <li
                  key={`${item.kind}-${item.id}`}
                  className="border-b border-stroke-subtle last:border-b-0"
                >
                  <button
                    onClick={() => setSelected(item.id)}
                    className={cn(
                      "focus-ring flex w-full items-start gap-sp-6 px-sp-7 py-sp-6 text-left transition-colors duration-200",
                      on ? "bg-surface-3" : "hover:bg-surface-2",
                    )}
                  >
                    <span className="mt-sp-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                      <Icon size={15} strokeWidth={1.5} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="t-body-strong block truncate text-ink-1">{item.title}</span>
                      <span className="t-caption mt-sp-2 line-clamp-2 block text-ink-4">
                        {item.caption}
                      </span>
                    </span>
                    <span className="t-mono-s shrink-0 pt-sp-2 text-ink-5">
                      {relative(item.at)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {active?.conversation ? (
            <ConversationDetailPanel sessionId={active.conversation.session_id} />
          ) : active?.request ? (
            <RequestDetailPanel item={active.request} />
          ) : active?.callback ? (
            <CallbackDetailPanel item={active.callback} />
          ) : null}
        </div>
      )}
    </div>
  );
}
