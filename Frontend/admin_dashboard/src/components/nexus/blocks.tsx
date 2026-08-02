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
  delta: number;
  context: string;
  series?: number[];
}) {
  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-start justify-between gap-sp-5">
        <p className="t-micro text-ink-5">{label}</p>
        <Delta value={delta} />
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
  delta: number;
  good?: boolean | null;
  context: string;
  meta?: string;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-sp-5">
        <p className="t-micro text-ink-5">{label}</p>
        <Delta value={delta} good={good ?? null} />
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
  const values = data.flatMap((d) => [d.current, d.previous]);
  const max = Math.max(...values) * 1.08;
  const step = 100 / (data.length - 1);
  const path = (key: "current" | "previous") =>
    data.map((d, i) => `${i * step},${100 - (d[key] / max) * 100}`).join(" ");

  return (
    <div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="h-[220px] w-full"
        aria-hidden="true"
      >
        {[0, 25, 50, 75, 100].map((y) => (
          <line
            key={y}
            x1="0"
            x2="100"
            y1={y}
            y2={y}
            stroke="var(--stroke-subtle)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        ))}
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
      </svg>
      <div className="mt-sp-4 flex justify-between">
        {data.map((d) => (
          <span key={d.day} className="t-micro text-ink-5">
            {d.day}
          </span>
        ))}
      </div>
    </div>
  );
}

export function BarChart({ data }: { data: { week: string; ai: number; advisor: number }[] }) {
  return (
    <div className="flex h-[220px] items-end gap-sp-6">
      {data.map((d) => (
        <div key={d.week} className="flex flex-1 flex-col items-center gap-sp-4">
          <div className="flex h-full w-full items-end justify-center gap-sp-2">
            <span
              className="w-1/3 rounded-t-[4px] bg-n-12"
              style={{ height: `${d.ai}%` }}
              aria-hidden="true"
            />
            <span
              className="w-1/3 rounded-t-[4px] bg-n-7"
              style={{ height: `${d.advisor}%` }}
              aria-hidden="true"
            />
          </div>
          <span className="t-micro text-ink-5">{d.week}</span>
        </div>
      ))}
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
