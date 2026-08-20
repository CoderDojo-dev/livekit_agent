import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Frown,
  MessagesSquare,
  ShieldAlert,
} from "lucide-react";
import { Card, CardHeader, Segmented, EmptyState } from "@/components/nexus/primitives";
import { HeroStat, StatCard, LineChart, Legend, SectionHeading } from "@/components/nexus/blocks";
import { TelemetryTimeline } from "@/components/nexus/telemetry-timeline";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getAnalyticsTrend } from "@/lib/api/analytics.server";
import { analyticsKeys } from "@/lib/nexus/query-keys";
import {
  dayLabel,
  deltaPct,
  deltaPoints,
  formatRatio,
  isChartable,
} from "@/lib/nexus/analytics-view";
import { formatCompact } from "@/lib/nexus/format";
import { errorMessage } from "@/lib/api/errors";
import { pageTitle } from "@/lib/nexus/brand";

export const Route = createFileRoute("/analytics")({
  head: () => ({
    meta: [
      { title: pageTitle("Analytics") },
      {
        name: "description",
        content: "Windowed volume and containment trends against the previous period.",
      },
      { property: "og:title", content: pageTitle("Analytics") },
      { property: "og:description", content: "Trend analysis across the support platform." },
    ],
  }),
  component: AnalyticsPage,
});

const RANGES = [
  { id: 7, label: "7d" },
  { id: 14, label: "14d" },
  { id: 30, label: "30d" },
] as const;

function AnalyticsPage() {
  const [days, setDays] = useState<number>(7);

  const trend = useQuery({
    queryKey: analyticsKeys.trend(days),
    queryFn: () => getAnalyticsTrend({ data: { days } }),
    placeholderData: keepPreviousData,
  });

  const rangeControl = (
    <Segmented
      items={RANGES.map((r) => r.label)}
      active={RANGES.find((r) => r.id === days)!.label}
      onSelect={(label) => setDays(RANGES.find((r) => r.label === label)!.id)}
    />
  );

  if (trend.isPending) {
    return (
      <PageSection index={0} className="grid gap-sp-6 md:grid-cols-2 xl:grid-cols-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </PageSection>
    );
  }

  if (trend.isError) {
    return (
      <PageSection index={0}>
        <Card>
          <ErrorState error={trend.error} onRetry={() => void trend.refetch()} />
        </Card>
      </PageSection>
    );
  }

  const { current, previous, daily } = trend.data;

  /* exactOptionalPropertyTypes: a present-but-undefined `delta` is a type error, so each
   * per-card delta is spread conditionally only when it has a value. */
  const sessionsDelta = deltaPct(current.total_sessions, previous.total_sessions);
  const containmentDelta = deltaPoints(
    current.containment_rate,
    previous.containment_rate,
    previous.total_sessions,
  );
  const escalationDelta = deltaPoints(
    current.escalation_rate,
    previous.escalation_rate,
    previous.total_sessions,
  );
  const frustrationDelta = deltaPct(current.avg_frustration, previous.avg_frustration);

  return (
    <>
      <PageSection index={0}>
        <SectionHeading
          title="Windowed performance"
          hint={`Compared with the preceding ${days} days`}
          icon={Activity}
        />
        <div className="grid gap-sp-6 md:grid-cols-2 xl:grid-cols-4">
          <HeroStat
            label={`Sessions (${days}d)`}
            value={formatCompact(current.total_sessions)}
            {...(sessionsDelta === undefined ? {} : { delta: sessionsDelta })}
            context={`Compared with the previous ${days} days`}
            series={daily.map((d) => d.current)}
            icon={MessagesSquare}
          />
          <StatCard
            label="Containment rate"
            value={formatRatio(current.containment_rate)}
            {...(containmentDelta === undefined ? {} : { delta: containmentDelta })}
            good
            context="Resolved without escalation"
            meta={`Previous: ${formatRatio(previous.containment_rate)}`}
            icon={CheckCircle2}
          />
          <StatCard
            label="Escalation rate"
            value={formatRatio(current.escalation_rate)}
            {...(escalationDelta === undefined ? {} : { delta: escalationDelta })}
            good={false}
            context="Handed to an advisor"
            meta={`Previous: ${formatRatio(previous.escalation_rate)}`}
            icon={ShieldAlert}
          />
          <StatCard
            label="Avg. frustration"
            value={current.avg_frustration.toFixed(2)}
            {...(frustrationDelta === undefined ? {} : { delta: frustrationDelta })}
            good={false}
            context="Mean peak frustration per session"
            meta={`Previous: ${previous.avg_frustration.toFixed(2)}`}
            icon={Frown}
          />
        </div>
      </PageSection>

      <PageSection index={1}>
        <Card>
          <CardHeader
            icon={BarChart3}
            title="Volume Trend"
            subtitle={`Daily sessions, ${trend.data.timezone}.`}
            action={
              <div className="flex items-center gap-sp-6">
                <Legend items={[{ label: "This period", strong: true }, { label: "Previous" }]} />
                {rangeControl}
              </div>
            }
          />
          <div className="mt-sp-7">
            {isChartable(daily) ? (
              <LineChart
                data={daily.map((d) => ({
                  day: dayLabel(d.day),
                  current: d.current,
                  previous: d.previous,
                }))}
              />
            ) : (
              <EmptyState
                icon={BarChart3}
                title="Not enough data"
                description={`No sessions were recorded in the last ${days} days.`}
              />
            )}
          </div>
        </Card>
      </PageSection>

      <PageSection index={2}>
        <TelemetryTimeline />
      </PageSection>
    </>
  );
}
