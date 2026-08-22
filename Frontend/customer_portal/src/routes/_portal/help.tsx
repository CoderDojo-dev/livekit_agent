import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowUpRight,
  AudioLines,
  Compass,
  Inbox,
  LifeBuoy,
  MessageCircleQuestion,
  ReceiptText,
  Shield,
} from "lucide-react";
import { brand, copy, pageTitle } from "@/lib/copy";
import { Button, Card, IconFrame, SectionLabel } from "@/components/portal/primitives";
import { Disclosure, PageSection } from "@/components/portal/data";

export const Route = createFileRoute("/_portal/help")({
  head: () => ({
    meta: [
      { title: pageTitle("Help") },
      {
        name: "description",
        content: "Browse help topics by theme, or hand the question to the assistant.",
      },
      { property: "og:title", content: brand.name },
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
      {/*
        THE TOPICS.

        These were five bare <Link>s carrying a class (`portal-section`) that
        did not exist and a type token (`t-body-l`) that did not exist either,
        so five of the page's five main targets rendered as unstyled text on an
        unstyled page. They are cards now: a real surface, a real border, a real
        hover, and the arrow that says the tile goes somewhere.
      */}
      <PageSection label={copy.help.browse} index={0}>
        <div className="grid gap-sp-5 sm:grid-cols-2">
          {HELP_TOPICS.map((topic) => {
            const t = copy.help.topics[topic.id];
            return (
              <Link
                key={topic.id}
                to={topic.to}
                className="focus-ring group block rounded-r-5"
                aria-label={t.title}
              >
                <Card interactive className="h-full p-sp-7">
                  <div className="flex items-start gap-sp-5">
                    <IconFrame icon={topic.icon} />
                    <div className="min-w-0 flex-1">
                      <p className="t-body-l text-ink-1">{t.title}</p>
                      <p className="t-caption mt-sp-2 text-ink-4">{t.body}</p>
                      {/* The action line holds its own row at rest and only
                          brightens, so nothing in the card moves on hover. */}
                      <span className="t-label mt-sp-5 inline-flex items-center gap-sp-3 text-ink-5 transition-colors duration-200 group-hover:text-ink-2">
                        {t.action}
                      </span>
                    </div>
                    <ArrowUpRight
                      size={15}
                      strokeWidth={1.6}
                      aria-hidden="true"
                      className="mt-sp-2 shrink-0 text-ink-5 opacity-0 transition-all duration-200 group-hover:-translate-y-px group-hover:translate-x-px group-hover:text-ink-2 group-hover:opacity-100"
                    />
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      </PageSection>

      {/*
        THE QUESTIONS.

        The page had no answers on it at all — every topic tile was a signpost
        to another screen, which meant a customer with a question had to leave
        Help to find out whether Help could help. Six disclosures, closed by
        default so the page still reads as a list, with the first one open
        because an accordion where nothing is open looks broken.
      */}
      <PageSection label={copy.help.faqHeading} index={1}>
        <Card className="p-sp-7">
          <p className="t-caption text-ink-4">{copy.help.faqIntro}</p>
          <div className="mt-sp-5">
            {copy.help.faq.map((entry, index) => (
              <Disclosure key={entry.q} question={entry.q} defaultOpen={index === 0}>
                <p className="t-body max-w-2xl text-ink-3">{entry.a}</p>
              </Disclosure>
            ))}
          </div>
        </Card>
      </PageSection>

      {/* THE EXITS. Two, in the order most customers want them. */}
      <PageSection index={2}>
        <Card className="flex flex-col gap-sp-7 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-sp-6">
            <IconFrame icon={MessageCircleQuestion} size="lg" tone="strong" />
            <div>
              <div className="t-micro text-ink-5">{copy.help.stillStuck}</div>
              <p className="t-body mt-sp-3 max-w-xl text-ink-3">{copy.help.contactBody}</p>
            </div>
          </div>
          <div className="flex shrink-0 gap-sp-4">
            <Link to="/assistant" className="focus-ring rounded-r-3">
              <Button variant="primary">
                <AudioLines size={15} strokeWidth={1.5} />
                {copy.help.talkToAssistant}
              </Button>
            </Link>
            <Link to="/requests" className="focus-ring rounded-r-3">
              <Button variant="secondary">
                <Inbox size={15} strokeWidth={1.5} />
                {copy.help.openRequest}
              </Button>
            </Link>
          </div>
        </Card>
      </PageSection>
    </div>
  );
}
