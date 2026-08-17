import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AudioLines,
  Compass,
  LifeBuoy,
  Layers2,
  ReceiptText,
  Shield,
  Accessibility,
  type LucideIcon,
} from "lucide-react";
import { copy } from "@/lib/copy";
import { Button, Card, SectionLabel } from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/help")({
  head: () => ({
    meta: [
      { title: "Help — Nexus Customer Portal" },
      {
        name: "description",
        content: "Browse help topics by theme, or hand the question to the assistant.",
      },
      { property: "og:title", content: "Help — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Answers, and a way to reach a person.",
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
  return (
    <div className="space-y-sp-9">
      <section className="space-y-sp-6">
        <SectionLabel>{copy.help.browse}</SectionLabel>
        <div className="grid gap-sp-6 sm:grid-cols-2">
          {copy.help.topics.map((t) => {
            const Icon = ICONS[t.icon] ?? Compass;
            return (
              <Card key={t.title} className="p-sp-7">
                <div className="flex items-start gap-sp-6">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-r-2 border border-stroke-subtle bg-surface-3 text-ink-3">
                    <Icon size={16} strokeWidth={1.5} />
                  </span>
                  <div className="min-w-0">
                    <div className="t-title-3 text-ink-1">{t.title}</div>
                    <p className="t-caption mt-sp-2 text-ink-4">{t.body}</p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
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
        <Link to="/assistant" className="shrink-0">
          <Button variant="primary">{copy.help.startConversation}</Button>
        </Link>
      </Card>
    </div>
  );
}
