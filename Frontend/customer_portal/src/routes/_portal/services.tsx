import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { copy } from "@/lib/copy";
import { plan, usage } from "@/lib/fixtures/services";
import { Card, Divider, Meter, SectionLabel, StatusChip } from "@/components/portal/primitives";

export const Route = createFileRoute("/_portal/services")({
  head: () => ({
    meta: [
      { title: "Services — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "See your Nexus plan, what it includes, and how much of your allowance you have used.",
      },
      { property: "og:title", content: "Services — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "Your plan and your usage in plain numbers.",
      },
    ],
  }),
  component: ServicesScreen,
});

function ServicesScreen() {
  return (
    <div className="space-y-sp-10">
      <section className="space-y-sp-6">
        <SectionLabel>{copy.services.plan}</SectionLabel>
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
              <div className="t-mono-s mt-sp-3 text-ink-5">{copy.services.renews(plan.renews)}</div>
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
              <Meter
                key={u.id}
                label={u.label}
                used={u.used}
                limit={u.limit}
                unit={u.unit}
                overNote={copy.services.overAllowance}
              />
            ))}
          </div>
        </Card>
      </section>
    </div>
  );
}
