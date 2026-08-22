import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowUpRight,
  AudioLines,
  Check,
  Cog,
  LockKeyhole,
  Mic,
  Minus,
  ShieldCheck,
  Waves,
  type LucideIcon,
} from "lucide-react";
import { brand, copy, pageTitle } from "@/lib/copy";
import { Card, Divider, IconFrame, SectionLabel, StatusChip } from "@/components/portal/primitives";
import { PageSection } from "@/components/portal/data";

export const Route = createFileRoute("/_portal/about")({
  head: () => ({
    meta: [
      { title: pageTitle("About the assistant") },
      {
        name: "description",
        content:
          "How the assistant works, what it can and cannot do, and exactly what happens to your voice and transcripts.",
      },
      { property: "og:title", content: brand.name },
      {
        property: "og:description",
        content: "What the assistant is, and what it is not.",
      },
    ],
  }),
  component: AboutScreen,
});

/** One glyph per step of copy.about.how, in the order the steps are written.
 *  Positional rather than keyed, because the steps are a narrative sequence and
 *  numbering them twice (n: "01" and a key) would be one number too many. */
const STEP_ICONS: LucideIcon[] = [Mic, Waves, Cog, ShieldCheck];

function AboutScreen() {
  return (
    <div className="mx-auto max-w-3xl space-y-sp-9">
      {/*
        THE MASTHEAD.

        Was a bare 12x12 plate, a 40px display line and a version stamp sitting
        directly on the page with nothing under them — the widest, emptiest band
        in the portal. It is a card now, at t-title-1 rather than t-display: this
        is a sentence about the product, not a headline number, and 40px on a
        768px column reads as a slide rather than as a page.
      */}
      <PageSection index={0}>
        <Card className="flex flex-col gap-sp-7 sm:flex-row sm:items-center">
          <div className="relative shrink-0">
            <div className="flex h-14 w-14 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-4 text-ink-1 shadow-elev-2">
              <AudioLines size={22} strokeWidth={1.5} aria-hidden="true" />
            </div>
            <span
              aria-hidden="true"
              className="absolute -inset-sp-3 rounded-r-4 border border-dashed border-stroke-subtle"
            />
          </div>
          <div className="min-w-0">
            <h2 className="t-title-1 text-ink-1">{copy.about.tagline}</h2>
            <div className="mt-sp-5 flex flex-wrap items-center gap-sp-4">
              <StatusChip tone="muted">{brand.version}</StatusChip>
              <StatusChip tone="outline">
                <LockKeyhole size={11} strokeWidth={1.5} />
                {copy.assistant.assurance.encrypted}
              </StatusChip>
              <StatusChip tone="dashed">{copy.assistant.assurance.noRecording}</StatusChip>
            </div>
          </div>
        </Card>
      </PageSection>

      <PageSection label={copy.about.howHeading} index={1}>
        <ol className="grid gap-sp-5 sm:grid-cols-2">
          {copy.about.how.map((step, index) => {
            const Icon = STEP_ICONS[index] ?? AudioLines;
            return (
              <li key={step.n}>
                <Card interactive className="group h-full p-sp-7">
                  <div className="flex items-center justify-between gap-sp-5">
                    <IconFrame icon={Icon} />
                    {/* The step number moves to the trailing edge and drops to
                        mono micro: it orders the cards without competing with
                        the four words that say what the step is. */}
                    <span className="t-mono-s text-ink-5">{step.n}</span>
                  </div>
                  <h3 className="t-title-3 mt-sp-6 text-ink-1">{step.t}</h3>
                  <p className="t-body mt-sp-3 text-ink-4">{step.b}</p>
                </Card>
              </li>
            );
          })}
        </ol>
      </PageSection>

      {/*
        CAN / CANNOT.

        Two bare <ul>s on the page background, which put the single most
        reassuring content in the portal — the list of things the assistant is
        structurally unable to do — on the same visual level as a caption. One
        card each, so the two columns read as a pair of statements.
      */}
      <PageSection index={2}>
        <div className="grid gap-sp-5 md:grid-cols-2">
          <Card className="p-sp-7">
            <SectionLabel>{copy.about.canHeading}</SectionLabel>
            <ul className="mt-sp-6 space-y-sp-5">
              {copy.about.can.map((entry) => (
                <li key={entry} className="t-ui flex items-start gap-sp-5 text-ink-2">
                  <span
                    aria-hidden="true"
                    className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-r-1 border border-stroke-strong bg-surface-3 text-ink-2"
                  >
                    <Check size={12} strokeWidth={1.8} />
                  </span>
                  {entry}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="p-sp-7">
            <SectionLabel>{copy.about.cannotHeading}</SectionLabel>
            <ul className="mt-sp-6 space-y-sp-5">
              {copy.about.cannot.map((entry) => (
                <li key={entry} className="t-ui flex items-start gap-sp-5 text-ink-4">
                  {/* Dashed, not filled: the shape carries the negative, since
                      nothing in this product may state a status by hue. */}
                  <span
                    aria-hidden="true"
                    className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-r-1 border border-dashed border-stroke-strong text-ink-5"
                  >
                    <Minus size={12} strokeWidth={1.8} />
                  </span>
                  {entry}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </PageSection>

      <PageSection label={copy.about.dataHeading} index={3}>
        <Card>
          <div className="flex items-start gap-sp-6">
            <IconFrame icon={ShieldCheck} size="lg" tone="strong" />
            <p className="t-body text-ink-3">{copy.about.dataBody}</p>
          </div>
        </Card>
      </PageSection>

      {/* The page ended on three static words with nowhere to go. The one thing
          a reader who has just finished "what it can do" wants is the thing
          itself. */}
      <PageSection index={4}>
        <Link
          to="/assistant"
          className="focus-ring group inline-flex items-center gap-sp-4 rounded-r-3 border border-stroke-default bg-surface-2 px-sp-6 py-sp-5 text-ink-2 transition-colors duration-200 hover:border-stroke-strong hover:bg-surface-3 hover:text-ink-1"
        >
          <AudioLines size={15} strokeWidth={1.5} aria-hidden="true" />
          <span className="t-ui">{copy.help.talkToAssistant}</span>
          <ArrowUpRight
            size={14}
            strokeWidth={1.6}
            aria-hidden="true"
            className="transition-transform duration-200 group-hover:-translate-y-px group-hover:translate-x-px"
          />
        </Link>
      </PageSection>

      <Divider />

      <footer className="t-caption flex gap-sp-7 pb-sp-9 text-ink-5">
        {copy.about.footer.map((f) => (
          <span key={f}>{f}</span>
        ))}
      </footer>
    </div>
  );
}
