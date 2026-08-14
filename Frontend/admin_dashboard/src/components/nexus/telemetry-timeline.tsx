import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Card, CardHeader, EmptyState, Segmented } from "@/components/nexus/primitives";
import { SeriesChart } from "@/components/nexus/blocks";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { getVerdictDistribution } from "@/lib/api/decisions.server";
import { analyticsKeys } from "@/lib/nexus/query-keys";
import { dispositionLabel } from "@/lib/nexus/call-view";
import { formatInteger } from "@/lib/nexus/format";
import {
  TELEMETRY_METRICS,
  averageOf,
  axisTicks,
  dispositionTally,
  dispositionTone,
  formatMetric,
  isPlottable,
  metricMax,
  metricUnit,
  metricValues,
  timelineSpan,
} from "@/lib/nexus/telemetry-view";
import type { TelemetryMetric } from "@/lib/nexus/telemetry-view";
import { cn } from "@/lib/utils";

/** Fixed readout row. Deliberately not a floating tooltip: the chart's coordinate space is
 *  stretched by preserveAspectRatio="none", and a static row cannot clip or overflow. */
function Readout({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div className="mt-sp-6 flex flex-wrap gap-x-sp-7 gap-y-sp-4 border-t border-stroke-subtle pt-sp-5">
      {items.map((item) => (
        <div key={item.label}>
          <p className="t-micro text-ink-5">{item.label}</p>
          <p className="t-ui mt-sp-2 text-ink-1">{item.value}</p>
        </div>
      ))}
    </div>
  );
}

/** The 50 most recent recorded sessions from /api/v1/telemetry/timeline.
 *
 *  This component adds NO network traffic: it reuses the exact query key Overview already uses
 *  for the verdict mix, so the two screens share one cache entry and one request. That is why
 *  queryKeys.supervision.telemetryTimeline stays unused — a second key would mean a second
 *  fetch of a byte-identical response. */
export function TelemetryTimeline() {
  const [metric, setMetric] = useState<TelemetryMetric>("duration");
  const [hovered, setHovered] = useState<number | null>(null);

  const telemetry = useQuery({
    queryKey: analyticsKeys.verdicts(),
    queryFn: () => getVerdictDistribution(),
  });

  /* Label round-trip: the house Segmented idiom is keyed by label, not id. */
  const control = (
    <Segmented
      items={TELEMETRY_METRICS.map((option) => option.label)}
      active={TELEMETRY_METRICS.find((option) => option.id === metric)!.label}
      onSelect={(label) => setMetric(TELEMETRY_METRICS.find((o) => o.label === label)!.id)}
    />
  );

  if (telemetry.isPending) return <CardSkeleton lines={6} />;

  if (telemetry.isError) {
    return <ErrorState error={telemetry.error} onRetry={() => void telemetry.refetch()} />;
  }

  const timeline = telemetry.data.timeline;

  if (!isPlottable(timeline)) {
    return (
      <Card>
        <CardHeader
          title="Session Telemetry"
          subtitle="Call length and peak frustration across the most recent sessions."
        />
        <div className="mt-sp-7">
          <EmptyState
            icon={Activity}
            title="Not enough telemetry"
            description="At least two recorded sessions are needed before a timeline can be drawn."
          />
        </div>
      </Card>
    );
  }

  const values = metricValues(timeline, metric);
  const max = metricMax(values);
  const ticks = axisTicks(timeline);
  const tally = dispositionTally(timeline);
  const point = hovered === null ? null : timeline[hovered]!;
  const scope = `the last ${formatInteger(timeline.length)} recorded sessions, oldest first`;

  /* Idle: the shape of the window. Hovered: BOTH series for that session, so switching the
   * plotted metric never hides the other number. */
  const readout =
    point === null
      ? [
          { label: "Sessions", value: formatInteger(timeline.length) },
          { label: "Average", value: formatMetric(metric, averageOf(values)) },
          { label: "Peak", value: formatMetric(metric, Math.max(...values)) },
          { label: "Window", value: timelineSpan(timeline) },
        ]
      : [
          { label: "Time", value: point.timestamp },
          { label: "Duration", value: formatMetric("duration", point.duration) },
          { label: "Frustration", value: formatMetric("frustration", point.frustration) },
          { label: "Outcome", value: dispositionLabel(point.disposition) },
        ];

  return (
    <Card>
      <CardHeader
        title="Session Telemetry"
        subtitle={`${metricUnit(metric)} across ${scope}.`}
        action={control}
      />

      <Readout items={readout} />

      <div className="mt-sp-7">
        <SeriesChart
          values={values}
          max={max}
          ticks={ticks}
          hovered={hovered}
          onHover={setHovered}
        />
      </div>

      {/* Outcome band — one segment per session, column-aligned with the series above, so the
          shape of the curve can be read against how those calls actually ended. */}
      <div
        className="mt-sp-6 flex gap-[2px]"
        onMouseLeave={() => setHovered(null)}
        aria-hidden="true"
      >
        {timeline.map((session, index) => (
          <span
            key={index}
            onMouseEnter={() => setHovered(index)}
            className={cn(
              "block h-[6px] flex-1 rounded-[1px] transition-opacity",
              dispositionTone(session.disposition),
              hovered === null || hovered === index ? "opacity-100" : "opacity-40",
            )}
          />
        ))}
      </div>

      <div className="mt-sp-5 flex flex-wrap items-center gap-x-sp-6 gap-y-sp-3">
        {tally.map((slice) => (
          <span key={slice.key} className="inline-flex items-center gap-sp-3">
            <span
              aria-hidden="true"
              className={cn("block h-[6px] w-[14px] rounded-[1px]", slice.tone)}
            />
            <span className="t-caption text-ink-4">{slice.label}</span>
            <span className="t-caption text-ink-2">{formatInteger(slice.count)}</span>
          </span>
        ))}
      </div>
    </Card>
  );
}
