import { createFileRoute } from "@tanstack/react-router";
import { Card, CardHeader } from "@/components/nexus/primitives";
import { HeroStat, StatCard, LineChart, BarChart, Legend } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import {
  OVERVIEW_STATS,
  CALL_VOLUME_SERIES,
  RESOLUTION_SERIES,
  HERO_SPARKLINE,
} from "@/lib/nexus/data";

export const Route = createFileRoute("/analytics")({
  head: () => ({
    meta: [
      { title: "Analytics — Nexus" },
      { name: "description", content: "Deeper trends on volume, resolution and handling performance." },
      { property: "og:title", content: "Analytics — Nexus" },
      { property: "og:description", content: "Trend analysis across the support platform." },
    ],
  }),
  component: AnalyticsPage,
});

function AnalyticsPage() {
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
            title="Volume Trend"
            subtitle="Week over week."
            action={<Legend items={[{ label: "This week", strong: true }, { label: "Last week" }]} />}
          />
          <div className="mt-sp-7">
            <LineChart data={CALL_VOLUME_SERIES} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Resolution Mix" subtitle="AI versus advisor share." />
          <div className="mt-sp-7">
            <BarChart data={RESOLUTION_SERIES} />
          </div>
        </Card>
      </PageSection>
    </>
  );
}
