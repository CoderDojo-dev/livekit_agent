import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { copy } from "@/lib/copy";
import { plan, usage, addons, available } from "@/lib/fixtures/services";
import {
  Button,
  Card,
  Divider,
  Meter,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: "Services — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "See your Nexus plan, what it includes, how much of your allowance you have used, and the add-ons available to you.",
      },
      { property: "og:title", content: "Services — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your plan, your add-ons, and your usage in plain numbers.",
      },
    ],
  }),
  component: ServicesScreen,
});

function ServicesScreen() {
  return (
    <div className="space-y-sp-10">
      <section className="space-y-sp-6">
        <SectionLabel right={<Button variant="quiet" size="sm">{copy.services.compare}</Button>}>
          {copy.services.plan}
        </SectionLabel>
        <Card>
          <div className="flex flex-col gap-sp-7 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-sp-5">
                <h3 className="t-metric-l text-ink-1">{plan.name}</h3>
                <StatusChip tone="solid">ACTIVE</StatusChip>
              </div>
              <p className="t-body mt-sp-3 max-w-xl text-ink-4">{plan.description}</p>
            </div>
            <div className="text-right">
              <div className="t-metric-xl text-ink-1">{plan.price}</div>
              <div className="t-caption text-ink-4">{plan.period}</div>
              <div className="t-mono-s mt-sp-3 text-ink-5">
                {copy.services.renews(plan.renews)}
              </div>
            </div>
          </div>

          <Divider className="my-sp-8" />

          <ul className="grid gap-sp-5 sm:grid-cols-2">
            {plan.included.map((f) => (
              <li key={f} className="t-ui flex items-start gap-sp-4 text-ink-2">
                <Check size={15} strokeWidth={1.5} className="mt-sp-2 shrink-0 text-ink-4" />
                {f}
              </li>
            ))}
          </ul>

          <Divider className="my-sp-8" />

          <div className="divide-y divide-stroke-subtle">
            {usage.map((u) => (
              <Meter key={u.id} label={u.label} used={u.used} limit={u.limit} unit={u.unit} />
            ))}
          </div>
        </Card>
      </section>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.services.addons}</SectionLabel>
        <div className="grid gap-sp-6 md:grid-cols-2">
          {addons.map((a) => (
            <Card key={a.id} className="flex flex-col justify-between p-sp-7">
              <div>
                <div className="flex items-start justify-between gap-sp-5">
                  <h3 className="t-title-3 text-ink-1">{a.name}</h3>
                  <StatusChip tone="outline">ON</StatusChip>
                </div>
                <p className="t-caption mt-sp-3 text-ink-4">{a.description}</p>
              </div>
              <div className="mt-sp-7 flex items-end justify-between">
                <div>
                  <div className="t-mono-l text-ink-1">{a.price}</div>
                  <div className="t-mono-s text-ink-5">
                    {copy.services.added(a.since)}
                  </div>
                </div>
                <Button variant="quiet" size="sm">
                  {copy.services.manage}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-sp-6">
        <SectionLabel>{copy.services.available}</SectionLabel>
        <div className="grid gap-sp-6 md:grid-cols-3">
          {available.map((a) => (
            <Card key={a.id} className="flex flex-col justify-between p-sp-7">
              <div>
                <h3 className="t-title-3 text-ink-1">{a.name}</h3>
                <p className="t-caption mt-sp-3 text-ink-4">{a.description}</p>
              </div>
              <div className="mt-sp-7 flex items-end justify-between">
                <div>
                  <div className="t-mono-l text-ink-2">{a.price}</div>
                  <div className="t-mono-s text-ink-5">{a.period}</div>
                </div>
                <Button variant="secondary" size="sm">
                  {copy.services.add}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
