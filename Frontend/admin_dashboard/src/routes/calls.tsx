import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Play, Download, Search } from "lucide-react";
import {
  Avatar,
  Button,
  Card,
  CardHeader,
  IconButton,
  SearchInput,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CALLS, CALL_KEYWORDS, CALL_SUMMARY, TRANSCRIPT, WAVEFORM } from "@/lib/nexus/data";
import { initials, maskPhone } from "@/lib/nexus/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/calls")({
  head: () => ({
    meta: [
      { title: "Call History & Transcripts — Nexus" },
      {
        name: "description",
        content: "End-of-call records, AI-generated summaries and full transcripts for every session.",
      },
      { property: "og:title", content: "Call History & Transcripts — Nexus" },
      { property: "og:description", content: "AI summaries and transcripts for customer calls." },
    ],
  }),
  component: CallsPage,
});

function CallsPage() {
  const [selected, setSelected] = useState(CALLS[0]!.id);
  const call = CALLS.find((c) => c.id === selected) ?? CALLS[0]!;

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[340px_1fr]">
      {/* Call list */}
      <Card padded={false} className="overflow-hidden">
        <div className="border-b border-stroke-subtle p-sp-6">
          <SearchInput placeholder="Search calls" />
        </div>
        <ul className="max-h-[720px] overflow-y-auto">
          {CALLS.map((c) => {
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
                  <Avatar initials={initials(c.name)} name={c.name} />
                  <span className="min-w-0 flex-1">
                    <span className="t-ui block truncate text-ink-1">{c.name}</span>
                    <span className="t-mono-s block truncate text-ink-4">{maskPhone(c.phone)}</span>
                  </span>
                  <span className="text-right">
                    <span className="t-mono-s block text-ink-3">{c.duration}</span>
                    <span className="t-caption block text-ink-5">{c.day}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* Detail */}
      <div className="space-y-sp-6">
        <Card>
          <div className="flex flex-wrap items-start gap-sp-6">
            <Avatar initials={initials(call.name)} name={call.name} size="xl" />
            <div className="min-w-0">
              <h2 className="t-title-2 text-ink-1">{call.name}</h2>
              <p className="t-mono-s mt-sp-2 text-ink-4">
                {call.uid} · {maskPhone(call.phone)}
              </p>
              <div className="mt-sp-5 flex flex-wrap gap-sp-4">
                <Token>{call.duration}</Token>
                <Token>
                  {call.day} {call.time}
                </Token>
              </div>
            </div>
            <div className="ml-auto flex gap-sp-4">
              <Button icon={Download} size="sm">
                Export
              </Button>
              <Button icon={Play} size="sm" variant="primary">
                Play recording
              </Button>
            </div>
          </div>

          {/* Waveform */}
          <div className="mt-sp-7 flex h-[64px] items-center gap-[2px] rounded-r-3 border border-stroke-subtle bg-surface-1 px-sp-5">
            {WAVEFORM.map((v, i) => (
              <span
                key={i}
                aria-hidden="true"
                className={cn("block w-[2px] rounded-[1px]", i < 42 ? "bg-n-12" : "bg-n-7")}
                style={{ height: `${Math.round(v * 44)}px` }}
              />
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="AI-Generated Summary" subtitle="Produced at end of call." />
          <ul className="mt-sp-6 space-y-sp-4">
            {CALL_SUMMARY.map((line) => (
              <li key={line} className="flex gap-sp-5">
                <span aria-hidden="true" className="mt-[9px] block size-[4px] shrink-0 bg-n-10" />
                <span className="t-body text-ink-2">{line}</span>
              </li>
            ))}
          </ul>
          <div className="mt-sp-7 flex flex-wrap gap-sp-4 border-t border-stroke-subtle pt-sp-6">
            {CALL_KEYWORDS.map((k) => (
              <Token key={k} mono={false}>
                {k}
              </Token>
            ))}
          </div>
        </Card>

        <Card padded={false}>
          <div className="flex items-center justify-between gap-sp-5 p-sp-7">
            <CardHeader title="Transcript" subtitle="Timestamped, speaker-attributed." />
            <IconButton label="Search transcript" icon={Search} />
          </div>
          <ul>
            {TRANSCRIPT.map((turn, i) => (
              <li key={i} className="border-t border-stroke-subtle px-sp-7 py-sp-6">
                <div className="flex items-center gap-sp-4">
                  <span className="t-mono-s text-ink-5">{turn.at}</span>
                  <span className="t-micro text-ink-4">{turn.speaker}</span>
                </div>
                <p className="t-body mt-sp-3 text-ink-2">{turn.text}</p>
                {turn.entities.length ? (
                  <div className="mt-sp-4 flex flex-wrap gap-sp-3">
                    {turn.entities.map((e) => (
                      <Token key={e} mono={false}>
                        {e}
                      </Token>
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </PageSection>
  );
}
