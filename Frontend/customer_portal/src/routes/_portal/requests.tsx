import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { copy } from "@/lib/copy";
import { requests, type RequestStatus } from "@/lib/fixtures/requests";
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

const TONE: Record<RequestStatus, "solid" | "outline" | "dashed" | "muted"> = {
  open: "dashed",
  in_progress: "solid",
  resolved: "outline",
  closed: "muted",
};

function RequestsScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("active");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(requests[0]!.id);

  const list = useMemo(
    () =>
      requests.filter((r) => {
        const isActive = r.status === "open" || r.status === "in_progress";
        const byTab =
          tab === "all" ? true : tab === "active" ? isActive : !isActive;
        const byQuery =
          query.trim() === "" ||
          (r.title + r.summary + r.ref).toLowerCase().includes(query.toLowerCase());
        return byTab && byQuery;
      }),
    [tab, query],
  );

  const attention = requests.find((r) => r.needsYou);
  const active = list.find((r) => r.id === selected) ?? list[0];

  return (
    <div className="space-y-sp-9">
      {attention && (
        <Card className="flex flex-col gap-sp-7 border-dashed md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="t-micro text-ink-5">{copy.requests.heroLabel}</div>
            <h2 className="t-title-1 mt-sp-4 text-ink-1">{attention.title}</h2>
            <p className="t-body mt-sp-3 max-w-2xl text-ink-4">
              {attention.events[attention.events.length - 1]?.body ?? attention.summary}
            </p>
            <div className="t-mono-s mt-sp-6 flex gap-sp-6 text-ink-5">
              <span>{attention.ref}</span>
              <span>Updated {attention.updated}</span>
            </div>
          </div>
          <Button variant="primary" onClick={() => setSelected(attention.id)}>
            {copy.requests.open}
          </Button>
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-sp-5">
        <Tabs tabs={TABS} value={tab} onChange={setTab} />
        <SearchField
          placeholder={copy.requests.search}
          value={query}
          onChange={setQuery}
          className="max-w-xs"
        />
        <Button variant="secondary" className="ml-auto">
          {copy.requests.create}
        </Button>
      </div>

      {list.length === 0 ? (
        <EmptyState
          title={copy.empty.filtered.title}
          body={copy.empty.filtered.body}
          action={
            <Button variant="secondary" onClick={() => { setQuery(""); setTab("all"); }}>
              {copy.empty.filtered.action}
            </Button>
          }
        />
      ) : (
        <div className="grid gap-sp-7 lg:grid-cols-[minmax(0,1fr)_440px]">
          <ul className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
            {list.map((r) => (
              <li key={r.id} className="border-b border-stroke-subtle last:border-b-0">
                <button
                  onClick={() => setSelected(r.id)}
                  className={cn(
                    "focus-ring w-full px-sp-7 py-sp-6 text-left transition-colors duration-200",
                    active?.id === r.id ? "bg-surface-3" : "hover:bg-surface-2",
                  )}
                >
                  <div className="flex items-center gap-sp-5">
                    <span className="t-mono-s text-ink-5">{r.ref}</span>
                    <StatusChip tone={TONE[r.status]}>
                      {copy.requests.status[r.status]}
                    </StatusChip>
                    <span className="t-mono-s ml-auto text-ink-5">{r.opened}</span>
                  </div>
                  <div className="t-body-strong mt-sp-4 text-ink-1">{r.title}</div>
                  <div className="t-caption mt-sp-2 text-ink-4">{r.summary}</div>
                </button>
              </li>
            ))}
          </ul>

          {active && (
            <Card className="lg:sticky lg:top-24 lg:self-start">
              <SectionLabel right={<StatusChip tone={TONE[active.status]}>{copy.requests.status[active.status]}</StatusChip>}>
                {active.ref}
              </SectionLabel>
              <h3 className="t-title-2 mt-sp-6 text-ink-1">{active.title}</h3>
              <p className="t-body mt-sp-3 text-ink-4">{active.summary}</p>

              <Divider className="my-sp-7" />
              <div className="t-micro text-ink-4">{copy.requests.timeline}</div>
              <ol className="mt-sp-6 space-y-sp-7">
                {active.events.map((ev, i) => (
                  <li key={ev.id} className="relative pl-sp-8">
                    <span className="absolute left-sp-2 top-sp-3 h-1.5 w-1.5 bg-n-10" />
                    {i < active.events.length - 1 && (
                      <span className="absolute left-[10px] top-sp-6 h-full w-px bg-stroke-default" />
                    )}
                    <div className="t-ui text-ink-1">{ev.label}</div>
                    <div className="t-mono-s mt-sp-1 text-ink-5">{ev.at}</div>
                    {ev.body && <p className="t-body mt-sp-3 text-ink-3">{ev.body}</p>}
                  </li>
                ))}
              </ol>

              {(active.status === "open" || active.status === "in_progress") && (
                <>
                  <Divider className="my-sp-7" />
                  <textarea
                    rows={3}
                    placeholder={copy.requests.replyPlaceholder}
                    className="focus-ring t-body w-full resize-none rounded-r-3 border border-stroke-default bg-surface-2 p-sp-5 text-ink-1 placeholder:text-ink-5"
                  />
                  <div className="mt-sp-5 flex justify-end">
                    <Button variant="primary" size="sm">
                      {copy.requests.send}
                    </Button>
                  </div>
                </>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
