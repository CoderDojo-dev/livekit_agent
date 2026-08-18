import { createFileRoute, Link } from "@tanstack/react-router";
import { AudioLines, Compass, LifeBuoy, ReceiptText, Shield } from "lucide-react";
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

const HELP_TOPICS = [
  { id: "plan", icon: Compass, to: "/services" },
  { id: "bill", icon: ReceiptText, to: "/billing" },
  { id: "request", icon: LifeBuoy, to: "/requests" },
  { id: "security", icon: Shield, to: "/security" },
  { id: "assistant", icon: AudioLines, to: "/assistant" },
] as const;

function HelpScreen() {
  return (
    <div className="space-y-sp-9">
      <section className="space-y-sp-6">
        <SectionLabel>{copy.help.browse}</SectionLabel>
        <div className="grid gap-sp-4 sm:grid-cols-2">
          {HELP_TOPICS.map((topic) => {
            const Icon = topic.icon;
            const t = copy.help.topics[topic.id];
            return (
              <Link
                key={topic.id}
                to={topic.to}
                className="portal-section focus-ring group flex items-start gap-sp-4"
              >
                <Icon className="size-5 shrink-0 text-ink-3" aria-hidden />
                <div className="min-w-0">
                  <p className="t-body-l text-ink-1">{t.title}</p>
                  <p className="t-caption mt-sp-2 text-ink-4">{t.body}</p>
                  <span className="t-caption mt-sp-2 block text-ink-5 transition-colors group-hover:text-ink-3">
                    {t.action}
                  </span>
                </div>
              </Link>
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
            <div className="t-micro text-ink-5">{copy.help.stillStuck}</div>
            <p className="t-body mt-sp-3 max-w-xl text-ink-3">{copy.help.contactBody}</p>
          </div>
        </div>
        {/* Two real exits, in the order most customers want them. */}
        <div className="flex shrink-0 gap-sp-4">
          <Link to="/assistant">
            <Button>{copy.help.talkToAssistant}</Button>
          </Link>
          <Link to="/requests">
            <Button variant="secondary">{copy.help.openRequest}</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
