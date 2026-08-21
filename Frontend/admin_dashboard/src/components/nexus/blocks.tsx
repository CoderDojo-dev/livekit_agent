import { useState, type ReactNode } from "react";
import { Card, Delta, Sparkline } from "@/components/nexus/primitives";
import { cn } from "@/lib/utils";

type StatIcon = React.ComponentType<{ size?: number; strokeWidth?: number }>;

/**
 * The icon frame shared by every stat card and card header.
 *
 * Reuses EmptyState's bordered chip at a smaller size, so the whole product has exactly one way
 * of framing an icon — no new surface, radius or ink.
 */
function StatIconFrame({ icon: Icon }: { icon: StatIcon }) {
  return (
    <span className="inline-flex size-[28px] shrink-0 items-center justify-center rounded-r-2 border border-stroke-default bg-surface-3 text-ink-4 transition-colors duration-[120ms] group-hover:border-stroke-strong group-hover:text-ink-2">
      <Icon size={14} strokeWidth={1.5} />
    </span>
  );
}

export function HeroStat({
  label,
  value,
  delta,
  good,
  context,
  series,
  icon,
}: {
  label: string;
  value: string;
  delta?: number;
  good?: boolean | null;
  context: string;
  series?: number[] | undefined;
  icon?: StatIcon | undefined;
}) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-sp-5">
        <div className="flex min-w-0 items-center gap-sp-4">
          {icon ? <StatIconFrame icon={icon} /> : null}
          <p className="t-micro truncate text-ink-5">{label}</p>
        </div>
        {delta === undefined ? null : <Delta value={delta} good={good ?? null} />}
      </div>

      <p className="t-metric-xl mt-sp-7 text-ink-1">{value}</p>
      <p className="t-caption mt-sp-2 text-ink-4">{context}</p>

      {/* mt-auto pins the trend to the card's floor, so a row of cards with unequal context
       * lengths still aligns its sparklines — the thing that makes a KPI row read as one
       * instrument rather than four separate ones. */}
      {series ? <Sparkline values={series} className="mt-auto pt-sp-6" /> : null}
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
  icon,
  series,
}: {
  label: string;
  value: string;
  delta?: number;
  good?: boolean | null;
  context: string;
  meta?: string | undefined;
  icon?: StatIcon | undefined;
  /** Muted trend for a supporting card in a row led by a HeroStat. */
  series?: number[] | undefined;
}) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-sp-5">
        <div className="flex min-w-0 items-center gap-sp-4">
          {icon ? <StatIconFrame icon={icon} /> : null}
          <p className="t-micro truncate text-ink-5">{label}</p>
        </div>
        {delta === undefined ? null : <Delta value={delta} good={good ?? null} />}
      </div>

      <p className="t-metric-l mt-sp-7 text-ink-1">{value}</p>
      <p className="t-caption mt-sp-2 text-ink-4">{context}</p>

      {series ? <Sparkline values={series} muted className="mt-sp-6" /> : null}

      {meta ? (
        <p className="t-caption mt-auto border-t border-stroke-subtle pt-sp-5 text-ink-5">{meta}</p>
      ) : null}
    </Card>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-sp-6 md:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

/**
 * Band heading for a page composed of several thematic groups.
 *
 * Overview used to be one flat stack in which a platform total looked exactly as important as a
 * containment KPI. An eyebrow plus a hairline rule is the cheapest way to say "these belong
 * together, and they answer a different question from the band above".
 */
export function SectionHeading({
  title,
  hint,
  action,
  icon: Icon,
}: {
  title: string;
  hint?: string | undefined;
  action?: ReactNode | undefined;
  icon?: StatIcon | undefined;
}) {
  return (
    <div className="mb-sp-6 flex flex-wrap items-center gap-sp-5">
      <div className="flex min-w-0 items-center gap-sp-4">
        {Icon ? <Icon size={13} strokeWidth={1.5} /> : null}
        <h2 className="t-micro text-ink-4">{title}</h2>
      </div>
      {hint ? <span className="t-caption truncate text-ink-5">{hint}</span> : null}
      <span aria-hidden="true" className="h-px min-w-[24px] flex-1 bg-stroke-subtle" />
      {action}
    </div>
  );
}

/**
 * Proportional distribution across a small number of named parts.
 *
 * Replaces three equally-weighted StatCards for the policy verdict mix. Three cards implied three
 * independent metrics; this is ONE metric split three ways, and a stacked bar says so in a tenth
 * of the vertical space. Emphasis is carried by weight (n-12 vs n-8), never hue, so it holds
 * under the achromatic rule.
 */
export function ShareBar({
  parts,
  total,
}: {
  parts: { label: string; value: number; strong?: boolean }[];
  total: number;
}) {
  return (
    <div>
      <div className="flex h-[10px] w-full gap-[2px] overflow-hidden rounded-r-1">
        {total <= 0 ? (
          <span aria-hidden="true" className="block h-full w-full bg-surface-4" />
        ) : (
          parts.map((part) => (
            <span
              key={part.label}
              aria-hidden="true"
              className={cn("block h-full", part.strong ? "bg-n-12" : "bg-n-8")}
              /* flexGrow rather than width: a zero-value part collapses cleanly instead of
               * rendering a 0px sliver still surrounded by its 2px gap. */
              style={{ flexGrow: part.value, flexBasis: 0, minWidth: part.value > 0 ? 3 : 0 }}
            />
          ))
        )}
      </div>

      <div className="mt-sp-5 grid gap-sp-4 sm:grid-cols-3">
        {parts.map((part) => (
          <div key={part.label} className="flex items-baseline gap-sp-3">
            <span
              aria-hidden="true"
              className={cn(
                "mb-[2px] block h-[8px] w-[3px] shrink-0 rounded-[1px]",
                part.strong ? "bg-n-12" : "bg-n-8",
              )}
            />
            <span className="t-caption truncate text-ink-4">{part.label}</span>
            <span className="t-mono ml-auto text-ink-1">{part.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Charts (achromatic, SVG only) ---------- */

export function LineChart({
  data,
}: {
  data: { day: string; current: number; previous: number }[];
}) {
  /* Declared before the early returns: hooks must run unconditionally on every render.
   * State is internal here (unlike SeriesChart, whose hover is lifted) because every caller of
   * LineChart wants the same readout and none of them needs to observe the hovered index. */
  const [hovered, setHovered] = useState<number | null>(null);

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

  /* One label per point is unreadable past ~10 days; thinning keeps the first, the last and an
   * even spread between them. */
  const tickStride = Math.max(1, Math.ceil(data.length / 8));

  const singlePoint = data.length === 1;
  const step = singlePoint ? 0 : 100 / (data.length - 1);

  const path = (key: "current" | "previous") =>
    data.map((point, index) => `${index * step},${y(point[key])}`).join(" ");

  const guideX = hovered === null ? 0 : hovered * step;
  const active = hovered === null ? null : data[hovered];

  return (
    <div>
      <div className="relative h-[180px] w-full" onMouseLeave={() => setHovered(null)}>
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
              {/* Wash under the current series. Same 6% fill as SeriesChart, so the two charts on
               * /analytics read as one family. */}
              <polygon
                points={`0,100 ${path("current")} 100,100`}
                fill="var(--n-12)"
                fillOpacity="0.06"
              />
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
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}

          {active ? (
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
              {/* Markers are line segments, never circles: preserveAspectRatio="none" stretches
               * geometry horizontally, so a circle would render as an ellipse. */}
              <line
                x1={Math.max(0, guideX - 1.5)}
                x2={Math.min(100, guideX + 1.5)}
                y1={y(active.current)}
                y2={y(active.current)}
                stroke="var(--n-12)"
                strokeWidth="3"
                vectorEffect="non-scaling-stroke"
              />
            </>
          ) : null}
        </svg>

        {/* Equal-width hit cells: the SVG is stretched, so hover is resolved in DOM space. */}
        {singlePoint ? null : (
          <div className="absolute inset-0 flex" aria-hidden="true">
            {data.map((point, index) => (
              <div
                key={point.day}
                className="h-full flex-1"
                onMouseEnter={() => setHovered(index)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Axis labels thin out rather than overlapping: past ~10 points every label is unreadable,
       * so only every nth tick is drawn while the row keeps its full width. */}
      <div className="mt-sp-4 flex justify-between">
        {data.map((point, index) => (
          <span
            key={point.day}
            className={cn(
              "t-micro text-ink-5",
              index % tickStride === 0 || index === data.length - 1 ? "" : "invisible",
            )}
          >
            {point.day}
          </span>
        ))}
      </div>

      {/* Fixed readout row, not a floating tooltip: the coordinate space is stretched, and a
       * static row can neither clip nor overflow its card. Reserves its height always, so
       * hovering the chart never nudges the layout below it. */}
      <div className="mt-sp-6 flex min-h-[38px] flex-wrap gap-x-sp-7 gap-y-sp-3 border-t border-stroke-subtle pt-sp-5">
        {active ? (
          <>
            <Readout label="Day" value={active.day} />
            <Readout label="This period" value={String(active.current)} />
            <Readout label="Previous" value={String(active.previous)} muted />
          </>
        ) : (
          <span className="t-caption text-ink-5">Hover the chart for a daily readout.</span>
        )}
      </div>
    </div>
  );
}

function Readout({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <p className="t-micro text-ink-5">{label}</p>
      <p className={cn("t-ui mt-sp-1", muted ? "text-ink-3" : "text-ink-1")}>{value}</p>
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
      <div className="relative h-[180px] w-full" onMouseLeave={() => onHover(null)}>
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
