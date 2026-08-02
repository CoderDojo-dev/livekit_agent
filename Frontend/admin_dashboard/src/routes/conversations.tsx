import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Upload, Send, Paperclip } from "lucide-react";
import {
  Avatar,
  Button,
  Card,
  CardHeader,
  PresenceDot,
  SearchInput,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CONVERSATIONS, THREAD, INGESTED_FILES } from "@/lib/nexus/data";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/conversations")({
  head: () => ({
    meta: [
      { title: "Conversations & Ingestion — Nexus" },
      {
        name: "description",
        content: "Live and archived customer exchanges alongside the knowledge files the agent reads.",
      },
      { property: "og:title", content: "Conversations & Ingestion — Nexus" },
      { property: "og:description", content: "Live threads and knowledge ingestion in one view." },
    ],
  }),
  component: ConversationsPage,
});

function ConversationsPage() {
  const [selected, setSelected] = useState(CONVERSATIONS[0]!.id);
  const conversation = CONVERSATIONS.find((c) => c.id === selected) ?? CONVERSATIONS[0]!;
  const liveCount = CONVERSATIONS.filter((c) => c.live).length;

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[300px_1fr_320px]">
      {/* Conversation list */}
      <Card padded={false} className="overflow-hidden">
        <div className="flex items-center justify-between gap-sp-5 border-b border-stroke-subtle p-sp-6">
          <span className="t-micro text-ink-5">Threads</span>
          <span className="inline-flex items-center gap-sp-3">
            <PresenceDot />
            <span className="t-mono-s text-ink-3">{liveCount} live</span>
          </span>
        </div>
        <div className="border-b border-stroke-subtle p-sp-6">
          <SearchInput placeholder="Search conversations" />
        </div>
        <ul className="max-h-[640px] overflow-y-auto">
          {CONVERSATIONS.map((c) => {
            const active = c.id === selected;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  className={cn(
                    "flex w-full items-start gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5 text-left transition-colors duration-[120ms]",
                    active ? "bg-surface-3" : "hover:bg-surface-3/60",
                  )}
                >
                  <Avatar initials={c.initials} name={c.name} />
                  <span className="min-w-0 flex-1">
                    <span className="t-ui flex items-center gap-sp-3 truncate text-ink-1">
                      {c.name}
                      {c.live ? <PresenceDot /> : null}
                    </span>
                    <span className="t-caption block truncate text-ink-4">{c.preview}</span>
                  </span>
                  <span className="t-mono-s shrink-0 text-ink-5">{c.at}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* Thread */}
      <Card padded={false} className="flex flex-col">
        <div className="flex items-center gap-sp-5 border-b border-stroke-subtle p-sp-6">
          <Avatar initials={conversation.initials} name={conversation.name} size="md" />
          <div>
            <p className="t-title-3 text-ink-1">{conversation.name}</p>
            <p className="t-caption text-ink-4">
              {conversation.live ? "Live conversation" : "Archived conversation"}
            </p>
          </div>
        </div>

        <ul className="flex-1 space-y-sp-6 overflow-y-auto p-sp-7">
          {THREAD.map((b, i) => {
            const own = b.kind === "customer";
            return (
              <li key={i} className={cn("flex flex-col", own ? "items-start" : "items-end")}>
                <span className="t-micro mb-sp-3 text-ink-5">
                  {b.label} · {b.at}
                </span>
                <div
                  className={cn(
                    "max-w-[80%] rounded-r-4 px-sp-6 py-sp-5",
                    own
                      ? "border border-stroke-default bg-surface-3 text-ink-2"
                      : b.kind === "ai"
                        ? "bg-n-12 text-n-0"
                        : "border border-stroke-strong bg-surface-2 text-ink-1",
                  )}
                >
                  <p className="t-body">{b.text.replace(/§/g, "")}</p>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center gap-sp-5 border-t border-stroke-subtle p-sp-6">
          <Button icon={Paperclip} size="sm">
            Attach
          </Button>
          <input
            type="text"
            placeholder="Write a reply"
            className="h-[34px] flex-1 rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
          />
          <Button icon={Send} size="sm" variant="primary">
            Send
          </Button>
        </div>
      </Card>

      {/* Ingestion */}
      <Card padded={false}>
        <div className="p-sp-7">
          <CardHeader title="Ingestion" subtitle="Files the AI agent reads before answering." />
        </div>
        <div className="px-sp-7">
          <div className="flex flex-col items-center gap-sp-4 rounded-r-4 border border-dashed border-stroke-strong px-sp-6 py-sp-8 text-center">
            <Upload size={18} strokeWidth={1.5} className="text-ink-4" aria-hidden="true" />
            <p className="t-ui text-ink-2">Drop files to ingest</p>
            <p className="t-caption text-ink-5">PDF, DOCX, MD or TXT · up to 25 MB</p>
            <Button size="sm" className="mt-sp-2">
              Browse files
            </Button>
          </div>
        </div>
        <ul className="mt-sp-6">
          {INGESTED_FILES.map((f) => (
            <li key={f.name} className="border-t border-stroke-subtle px-sp-7 py-sp-5">
              <div className="flex items-start justify-between gap-sp-4">
                <div className="min-w-0">
                  <p className="t-mono truncate text-ink-1">{f.name}</p>
                  <p className="t-caption mt-sp-2 text-ink-5">{f.meta}</p>
                </div>
                <StatusChip status={f.status} />
              </div>
            </li>
          ))}
        </ul>
        <div className="border-t border-stroke-subtle px-sp-7 py-sp-5">
          <Token>{INGESTED_FILES.length} sources</Token>
        </div>
      </Card>
    </PageSection>
  );
}
