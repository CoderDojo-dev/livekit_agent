import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  AudioLines,
  Compass,
  LifeBuoy,
  Layers2,
  ReceiptText,
  Shield,
  Accessibility,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { copy } from "@/lib/copy";
import { topics, popular } from "@/lib/fixtures/help";
import {
  Button,
  Card,
  SearchField,
  SectionLabel,
} from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/help")({
  head: () => ({
    meta: [
      { title: "Help — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Search Nexus help articles by topic, read the most popular guides, or hand the question to the assistant.",
      },
      { property: "og:title", content: "Help — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Answers, guides, and a way to reach a person.",
      },
    ],
  }),
  component: HelpScreen,
});

const ICONS: Record<string, LucideIcon> = {
  compass: Compass,
  "audio-lines": AudioLines,
  "receipt-text": ReceiptText,
  "layers-2": Layers2,
  shield: Shield,
  accessibility: Accessibility,
};

function HelpScreen() {
  const [query, setQuery] = useState("");

  return (
    <div className="space-y-sp-10">
      <SearchField
        placeholder={copy.help.search}
        value={query}
        onChange={setQuery}
        className="h-11 max-w-2xl"
      />

      <section className="space-y-sp-6">
        <SectionLabel>{copy.help.browse}</SectionLabel>
        <div className="grid gap-sp-6 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((t) => {
            const Icon = ICONS[t.icon] ?? Compass;
            return (
              <Card
                key={t.id}
                className="flex cursor-pointer items-start gap-sp-6 p-sp-7 transition-colors duration-200 hover:bg-surface-2"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                  <Icon size={16} strokeWidth={1.5} />
                </span>
                <span className="min-w-0">
                  <span className="t-title-3 block text-ink-1">{t.name}</span>
                  <span className="t-caption text-ink-5">{copy.help.articles(t.count)}</span>
                </span>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.help.popular}</SectionLabel>
        <ul className="overflow-hidden rounded-r-5 border border-stroke-default bg-surface-1">
          {popular.map((a) => (
            <li key={a.id} className="border-b border-stroke-subtle last:border-b-0">
              <button className="focus-ring flex w-full items-center gap-sp-6 px-sp-7 py-sp-6 text-left transition-colors duration-200 hover:bg-surface-2">
                <span className="min-w-0 flex-1">
                  <span className="t-body-strong block truncate text-ink-1">{a.title}</span>
                  <span className="t-caption text-ink-5">
                    {a.topic} · {a.minutes} min read
                  </span>
                </span>
                <ChevronRight size={16} strokeWidth={1.5} className="shrink-0 text-ink-5" />
              </button>
            </li>
          ))}
        </ul>
      </section>

      <Card className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-sp-6">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
            <LifeBuoy size={16} strokeWidth={1.5} />
          </span>
          <div>
            <div className="t-micro text-ink-5">{copy.help.contactLabel}</div>
            <p className="t-body mt-sp-3 max-w-xl text-ink-3">{copy.help.contactBody}</p>
          </div>
        </div>
        <div className="flex shrink-0 gap-sp-4">
          <Button variant="primary">{copy.help.startConversation}</Button>
          <Button variant="quiet">{copy.help.createRequest}</Button>
        </div>
      </Card>
    </div>
  );
}
