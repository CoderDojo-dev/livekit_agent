import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AudioLines, Inbox, PhoneCall } from "lucide-react";
import { copy } from "@/lib/copy";
import { interactions, type Interaction } from "@/lib/fixtures/interactions";
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
};

function ActivityScreen() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string>(interactions[0]!.id);

  const list = useMemo(
    () =>
      interactions.filter(
        (i) =>
          (tab === "all" || i.kind === tab) &&
          (query.trim() === "" ||
            (i.title + i.summary).toLowerCase().includes(query.toLowerCase())),
      ),
    [tab, query],
  );

  const hero = interactions[0]!;
  const active: Interaction | undefined = list.find((i) => i.id === selected) ?? list[0];

  return (
    <div className="space-y-sp-9">
      {/* --- l'entete de reprise, 30.2 ------------------------------------ */}
      <Card className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <div className="t-micro text-ink-5">{copy.activity.heroLabel}</div>
          <h2 className="t-title-1 mt-sp-4 truncate text-ink-1">{hero.title}</h2>
          <p className="t-body mt-sp-3 max-w-2xl text-ink-4">{hero.summary}</p>
          <div className="t-mono-s mt-sp-6 flex flex-wrap gap-sp-6 text-ink-5">
            <span>{hero.at}</span>
            <span>
              {hero.duration} {copy.activity.duration}
            </span>
            <span>
              {hero.turns} {copy.activity.turns}
            </span>
            <span>
              {hero.actions} {copy.activity.actions}
            </span>
          </div>
        </div>
        <Button variant="primary" onClick={() => setSelected(hero.id)}>
          {copy.activity.open}
        </Button>
      </Card>

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
          {/* --- la liste --------------------------------------------------- */}
          <ul className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
            {list.map((item) => {
              const Icon = KIND_ICON[item.kind];
              const on = active?.id === item.id;
              return (
                <li key={item.id} className="border-b border-stroke-subtle last:border-b-0">
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
                        {item.summary}
                      </span>
                    </span>
                    <span className="t-mono-s shrink-0 pt-sp-2 text-ink-5">{item.relative}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          {/* --- le detail -------------------------------------------------- */}
          {active ? (
            <Card className="lg:sticky lg:top-24 lg:self-start">
              <SectionLabel
                right={
                  <StatusChip tone={active.changed.length ? "solid" : "outline"}>
                    {active.changed.length ? "CHANGED" : "NO CHANGES"}
                  </StatusChip>
                }
              >
                {active.kind.toUpperCase()}
              </SectionLabel>
              <h3 className="t-title-2 mt-sp-6 text-ink-1">{active.title}</h3>
              <p className="t-body mt-sp-3 text-ink-4">{active.summary}</p>
              <Divider className="my-sp-7" />
              <dl className="grid grid-cols-3 gap-sp-5">
                {[
                  ["WHEN", active.at],
                  ["LENGTH", active.duration ?? "—"],
                  ["ACTIONS", String(active.actions)],
                ].map(([k, v]) => (
                  <div key={k}>
                    <dt className="t-micro-2 text-ink-5">{k}</dt>
                    <dd className="t-mono mt-sp-2 text-ink-2">{v}</dd>
                  </div>
                ))}
              </dl>

              {active.changed.length > 0 && (
                <>
                  <Divider className="my-sp-7" />
                  <div className="t-micro text-ink-4">{copy.assistant.summary.changed}</div>
                  <ul className="mt-sp-4 space-y-sp-3">
                    {active.changed.map((c) => (
                      <li key={c} className="t-ui flex gap-sp-4 text-ink-2">
                        <span className="mt-sp-4 h-1 w-3 shrink-0 bg-n-9" />
                        {c}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {active.transcript.length > 0 && (
                <>
                  <Divider className="my-sp-7" />
                  <div className="t-micro text-ink-4">TRANSCRIPT</div>
                  <div className="mt-sp-6 max-h-72 space-y-sp-6 overflow-y-auto pr-sp-3">
                    {active.transcript.map((line, i) => (
                      <div key={i}>
                        <div className="t-micro-2 mb-sp-2 flex gap-sp-4 text-ink-5">
                          <span>{line.speaker.toUpperCase()}</span>
                          <span className="t-mono-s">{line.at}</span>
                        </div>
                        <p
                          className={cn(
                            "t-body",
                            line.speaker === "you" ? "text-ink-3" : "text-ink-1",
                          )}
                        >
                          {line.text}
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
          ) : null}
        </div>
      )}
    </div>
  );
}
