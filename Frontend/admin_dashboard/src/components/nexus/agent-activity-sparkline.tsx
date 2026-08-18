import { Line, LineChart, ResponsiveContainer } from "recharts";
import type { AgentDailyPoint } from "@/lib/api/agents.server";
import { dailyTokenTotal } from "@/lib/nexus/agent-view";

export type AgentSparklineMetric = "duration" | "tokens";

export function AgentActivitySparkline({
  points,
  metric,
  label,
}: {
  points: AgentDailyPoint[];
  metric: AgentSparklineMetric;
  label: string;
}) {
  const data = points.map((point) => ({
    day: point.day,
    value: metric === "duration" ? point.attributed_call_duration_seconds : dailyTokenTotal(point),
  }));
  const available = data.some((point) => point.value !== null);
  if (!available) {
    return <span className="t-caption text-ink-4">Unavailable</span>;
  }
  return (
    <div role="img" aria-label={label} className="h-10 min-w-28 text-ink-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 4, left: 2 }}>
          <Line
            type="monotone"
            dataKey="value"
            stroke="currentColor"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
      <span className="sr-only">
        {data
          .map((point) => `${point.day}: ${point.value === null ? "unavailable" : point.value}`)
          .join(", ")}
      </span>
    </div>
  );
}
