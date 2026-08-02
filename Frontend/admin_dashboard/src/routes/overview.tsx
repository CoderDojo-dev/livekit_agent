import { createFileRoute } from "@tanstack/react-router";
import { Card, CardHeader, Avatar, StatusChip, PresenceDot } from "@/components/nexus/primitives";
import { HeroStat, StatCard, LineChart, BarChart, Legend } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import {
  OVERVIEW_STATS,
  CALL_VOLUME_SERIES,
  RESOLUTION_SERIES,
  HERO_SPARKLINE,
  BILLING_ACTIVITY,
  ADVISOR_TEAM,
} from "@/lib/nexus/data";

export const Route = createFileRoute("/overview")({
  head: () => ({
    meta: [
      { title: "Overview & Analytics — Nexus" },
      {
        name: "description",
        content: "Call volume, resolution rate, handle time and advisor availability at a glance.",
      },
      { property: "og:title", content: "Overview & Analytics — Nexus" },
      {
        property: "og:description",
        content: "Platform-wide support performance in a monochrome console.",
      },
    ],
  }),
  component: OverviewPage,
});

function OverviewPage() {
  const { hero, cards } = OVERVIEW_STATS;

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-4">
        <HeroStat
          label={hero.label}
          value={hero.value}
          delta={hero.delta}
          context={hero.context}
          series={HERO_SPARKLINE}
        />
        {cards.map((c) => (
          <StatCard key={c.label} {...c} />
        ))}
      </PageSection>

      <PageSection className="grid gap-sp-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Call Volume Over Time"
            subtitle="Current week compared with the previous week."
            action={<Legend items={[{ label: "This week", strong: true }, { label: "Last week" }]} />}
          />
          <div className="mt-sp-7">
            <LineChart data={CALL_VOLUME_SERIES} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Resolution Rates" subtitle="AI-resolved versus advisor-resolved." />
          <div className="mt-sp-7">
            <BarChart data={RESOLUTION_SERIES} />
          </div>
          <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
            <Legend items={[{ label: "AI agent", strong: true }, { label: "Advisor" }]} />
          </div>
        </Card>
      </PageSection>

      <PageSection className="grid gap-sp-6 xl:grid-cols-2">
        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader title="Billing Activity" subtitle="Latest invoice movements." />
          </div>
          <ul>
            {BILLING_ACTIVITY.map((b) => (
              <li
                key={b.email}
                className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
              >
                <Avatar initials={b.initials} name={b.name} />
                <div className="min-w-0">
                  <p className="t-ui truncate text-ink-1">{b.name}</p>
                  <p className="t-caption truncate text-ink-4">{b.email}</p>
                </div>
                <span className="t-mono-l ml-auto text-ink-1">{b.amount}</span>
                <StatusChip status={b.status} />
              </li>
            ))}
          </ul>
        </Card>

        <Card padded={false}>
          <div className="p-sp-7">
            <CardHeader title="Team Availability" subtitle="Advisors currently on the floor." />
          </div>
          <ul>
            {ADVISOR_TEAM.map((a) => (
              <li
                key={a.name}
                className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5"
              >
                <Avatar initials={a.initials} name={a.name} />
                <div className="min-w-0">
                  <p className="t-ui truncate text-ink-1">{a.name}</p>
                  <p className="t-caption inline-flex items-center gap-sp-3 text-ink-4">
                    <PresenceDot live={a.online} />
                    {a.presence}
                  </p>
                </div>
                <span className="t-label ml-auto text-ink-3">{a.role}</span>
              </li>
            ))}
          </ul>
        </Card>
      </PageSection>
    </>
  );
}
