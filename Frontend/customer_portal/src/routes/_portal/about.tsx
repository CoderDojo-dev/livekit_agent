import { createFileRoute } from "@tanstack/react-router";
import { Check, Minus } from "lucide-react";
import { brand, copy, pageTitle } from "@/lib/copy";
import { Card, Divider, SectionLabel } from "@/components/portal/primitives";

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

function AboutScreen() {
  return (
    <div className="mx-auto max-w-3xl space-y-sp-10">
      <header>
        <div className="flex h-12 w-12 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-4 shadow-elev-1">
          <span className="t-mono-l text-ink-1">C</span>
        </div>
        <h2 className="t-display mt-sp-7 text-ink-1">{copy.about.tagline}</h2>
        <p className="t-mono-s mt-sp-4 text-ink-5">{brand.version}</p>
      </header>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.about.howHeading}</SectionLabel>
        <ol className="grid gap-sp-6 sm:grid-cols-2">
          {copy.about.how.map((step) => (
            <Card key={step.n} className="p-sp-7">
              <div className="t-mono-s text-ink-5">{step.n}</div>
              <h3 className="t-title-3 mt-sp-4 text-ink-1">{step.t}</h3>
              <p className="t-body mt-sp-3 text-ink-4">{step.b}</p>
            </Card>
          ))}
        </ol>
      </section>

      <section className="grid gap-sp-7 md:grid-cols-2">
        <div className="space-y-sp-6">
          <SectionLabel>{copy.about.canHeading}</SectionLabel>
          <ul className="space-y-sp-4">
            {copy.about.can.map((c) => (
              <li key={c} className="t-ui flex items-start gap-sp-5 text-ink-2">
                <Check size={15} strokeWidth={1.5} className="mt-sp-2 shrink-0 text-ink-4" />
                {c}
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-sp-6">
          <SectionLabel>{copy.about.cannotHeading}</SectionLabel>
          <ul className="space-y-sp-4">
            {copy.about.cannot.map((c) => (
              <li key={c} className="t-ui flex items-start gap-sp-5 text-ink-4">
                <Minus size={15} strokeWidth={1.5} className="mt-sp-2 shrink-0 text-ink-5" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.about.dataHeading}</SectionLabel>
        <Card>
          <p className="t-body text-ink-3">{copy.about.dataBody}</p>
        </Card>
      </section>

      <Divider />

      <footer className="t-caption flex gap-sp-7 pb-sp-9 text-ink-5">
        {copy.about.footer.map((f) => (
          <span key={f}>{f}</span>
        ))}
      </footer>
    </div>
  );
}
