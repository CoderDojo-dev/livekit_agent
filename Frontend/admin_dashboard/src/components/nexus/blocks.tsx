import type { ReactNode } from "react";
import { Card, Delta, Sparkline } from "@/components/nexus/primitives";
import { cn } from "@/lib/utils";

export function HeroStat({
  label,
  value,
  delta,
  context,
  series,
}: {
  label: string;
  value: string;
  delta?: number;
  context: string;
  series?: number[];
}) {
  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-start justify-between gap-sp-5">
        <p className="t-micro text-ink-5">{label}</p>
        {delta === undefined ? null : <Delta value={delta} />}
      </div>
      <p className="t-metric-xl mt-sp-6 text-ink-1">{value}</p>
      <p className="t-caption mt-sp-2 text-ink-4">{context}</p>
      {series ? <Sparkline values={series} className="mt-sp-6" /> : null}
    </Card>
  );
}

export function StatCard({
  label,
  value,
  delta,
  good,
  context,
  meta,
}: {
  label: string;
  value: string;
  delta?: number;
  good?: boolean | null;
  context: string;
  meta?: string;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-sp-5">
        <p className="t-micro text-ink-5">{label}</p>
        {delta === undefined ? null : <Delta value={delta} good={good ?? null} />}
      </div>
      <p className="t-metric-l mt-sp-6 text-ink-1">{value}</p>
      <p className="t-caption mt-sp-2 text-ink-4">{context}</p>
      {meta ? (
        <p className="t-caption mt-sp-5 border-t border-stroke-subtle pt-sp-4 text-ink-5">{meta}</p>
      ) : null}
    </Card>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-sp-6 md:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

/* ---------- Charts (achromatic, SVG only) ---------- */

export function LineChart({
  data,
}: {
  data: { day: string; current: number; previous: number }[];
}) {
  if (data.length === 0) {
    return <p className="t-caption text-ink-4">No chart data.</p>;
  }

  const values = data.flatMap((point) => [point.current, point.previous]);

  if (values.some((value) => !Number.isFinite(value))) {
    return (
      <p role="status" className="t-caption text-ink-4">
        Chart data is unavailable.
      </p>
    );
  }

  const max = Math.max(1, ...values) * 1.08;
  const y = (value: number) => 100 - (value / max) * 100;

  const singlePoint = data.length === 1;
  const step = singlePoint ? 0 : 100 / (data.length - 1);

  const path = (key: "current" | "previous") =>
    data.map((point, index) => `${index * step},${y(point[key])}`).join(" ");

  return (
    <div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="h-[220px] w-full"
        aria-hidden="true"
      >
        {[0, 25, 50, 75, 100].map((gridline) => (
          <line
            key={gridline}
            x1="0"
            x2="100"
            y1={gridline}
            y2={gridline}
            stroke="var(--stroke-subtle)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {singlePoint ? (
          <>
            <line
              x1="48"
              x2="52"
              y1={y(data[0]!.previous)}
              y2={y(data[0]!.previous)}
              stroke="var(--n-8)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />
            <line
              x1="48"
              x2="52"
              y1={y(data[0]!.current)}
              y2={y(data[0]!.current)}
              stroke="var(--n-12)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </>
        ) : (
          <>
            <polyline
              points={path("previous")}
              fill="none"
              stroke="var(--n-8)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />
            <polyline
              points={path("current")}
              fill="none"
              stroke="var(--n-12)"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </>
        )}
      </svg>

      <div className="mt-sp-4 flex justify-between">
        {data.map((point) => (
          <span key={point.day} className="t-micro text-ink-5">
            {point.day}
          </span>
        ))}
      </div>
    </div>
  );
}

/** A single achromatic series with an optional hover guide — same SVG idiom as LineChart
 *  (viewBox 0 0 100 100, preserveAspectRatio="none", non-scaling strokes).
 *
 *  Differences from LineChart, all deliberate:
 *   - one series instead of two, with the scale supplied by the caller (metricMax) so an
 *     all-zero window degrades to a flat baseline instead of NaN geometry;
 *   - sparse x-axis ticks, because one label per point is unreadable past ~30 points;
 *   - hover state is LIFTED to the caller, which keeps this module stateless;
 *   - markers are lines, never circles: preserveAspectRatio="none" stretches geometry
 *     horizontally, so a circle would render as an ellipse.
 *
 *  Requires values.length >= 2 (the caller gates with isPlottable). */
export function SeriesChart({
  values,
  max,
  ticks,
  hovered,
  onHover,
}: {
  values: number[];
  max: number;
  ticks: { index: number; label: string }[];
  hovered: number | null;
  onHover: (index: number | null) => void;
}) {
  const step = 100 / (values.length - 1);
  const y = (value: number) => 100 - (value / max) * 100;
  const line = values.map((value, index) => `${index * step},${y(value)}`).join(" ");
  const area = `0,100 ${line} 100,100`;
  const guideX = hovered === null ? 0 : hovered * step;

  return (
    <div>
      <div className="relative h-[220px] w-full" onMouseLeave={() => onHover(null)}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="h-full w-full"
          aria-hidden="true"
        >
          {[0, 25, 50, 75, 100].map((gridline) => (
            <line
              key={gridline}
              x1="0"
              x2="100"
              y1={gridline}
              y2={gridline}
              stroke="var(--stroke-subtle)"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <polygon points={area} fill="var(--n-12)" fillOpacity="0.06" />
          <polyline
            points={line}
            fill="none"
            stroke="var(--n-12)"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
          {hovered === null ? null : (
            <>
              <line
                x1={guideX}
                x2={guideX}
                y1="0"
                y2="100"
                stroke="var(--n-8)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
              />
              <line
                x1={Math.max(0, guideX - 2)}
                x2={Math.min(100, guideX + 2)}
                y1={y(values[hovered]!)}
                y2={y(values[hovered]!)}
                stroke="var(--n-12)"
                strokeWidth="3"
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}
        </svg>
        {/* Equal-width hit cells: the SVG is stretched, so hover is resolved in DOM space. */}
        <div className="absolute inset-0 flex" aria-hidden="true">
          {values.map((_, index) => (
            <div key={index} className="h-full flex-1" onMouseEnter={() => onHover(index)} />
          ))}
        </div>
      </div>
      <div className="mt-sp-4 flex justify-between">
        {ticks.map((tick) => (
          <span key={tick.index} className="t-micro text-ink-5">
            {tick.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; strong?: boolean }[] }) {
  return (
    <div className="flex items-center gap-sp-6">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-sp-3">
          <span
            aria-hidden="true"
            className={cn("block h-[2px] w-[14px] rounded-[1px]", i.strong ? "bg-n-12" : "bg-n-8")}
          />
          <span className="t-caption text-ink-4">{i.label}</span>
        </span>
      ))}
    </div>
  );
}
