import { describe, expect, it, beforeEach, vi } from "vitest";
import { createElement, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import type { AgentDailyPoint } from "@/lib/api/agents.server";

const chartLog = vi.hoisted(() => ({
  charts: [] as unknown[],
  lines: [] as Record<string, unknown>[],
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) =>
    createElement("div", { "data-testid": "responsive" }, children),
  LineChart: ({ data, children }: { data: unknown; children: ReactNode }) => {
    chartLog.charts.push(data);
    return createElement("div", { "data-testid": "line-chart" }, children);
  },
  Line: (props: Record<string, unknown>) => {
    chartLog.lines.push(props);
    return createElement("path", { "data-testid": "line" });
  },
}));

import { AgentActivitySparkline } from "./agent-activity-sparkline";

function point(overrides: Partial<AgentDailyPoint>): AgentDailyPoint {
  return {
    day: "2026-08-17",
    attributed_calls: 1,
    attributed_call_duration_seconds: 120,
    provider_input_tokens: 10,
    provider_output_tokens: 20,
    ...overrides,
  };
}

function renderSparkline(
  points: AgentDailyPoint[],
  metric: "duration" | "tokens" = "duration",
  label = "Trend",
) {
  return render(
    createElement(AgentActivitySparkline, { points, metric, label }),
  );
}

describe("AgentActivitySparkline", () => {
  beforeEach(() => {
    chartLog.charts.length = 0;
    chartLog.lines.length = 0;
  });

  it("renders an accessible chart with the label and one line", () => {
    renderSparkline([point({})]);
    expect(screen.getByRole("img")).toHaveAttribute("aria-label", "Trend");
    expect(screen.getAllByTestId("line").length).toBe(1);
  });

  it("maps duration points to the attributed duration value", () => {
    renderSparkline([
      point({
        day: "2026-08-17",
        attributed_call_duration_seconds: 300,
        provider_input_tokens: null,
        provider_output_tokens: null,
      }),
    ]);
    expect(chartLog.charts).toEqual([
      [{ day: "2026-08-17", value: 300 }],
    ]);
  });

  it("maps token points to the summed daily provider total", () => {
    renderSparkline(
      [
        point({
          day: "2026-08-17",
          provider_input_tokens: 10,
          provider_output_tokens: 20,
        }),
      ],
      "tokens",
    );
    expect(chartLog.charts).toEqual([[{ day: "2026-08-17", value: 30 }]]);
  });

  it("keeps null values as gaps in the chart data", () => {
    renderSparkline(
      [
        point({ day: "2026-08-16", provider_input_tokens: null, provider_output_tokens: null }),
        point({ day: "2026-08-17", provider_input_tokens: 5, provider_output_tokens: 5 }),
      ],
      "tokens",
    );
    expect(chartLog.charts).toEqual([
      [
        { day: "2026-08-16", value: null },
        { day: "2026-08-17", value: 10 },
      ],
    ]);
    const line = chartLog.lines[0]!;
    expect(line["connectNulls"]).toBe(false);
  });

  it("disables line animation", () => {
    renderSparkline([point({})]);
    expect(chartLog.lines[0]!["isAnimationActive"]).toBe(false);
  });

  it("lists every date and value for screen readers", () => {
    renderSparkline(
      [
        point({ day: "2026-08-16" }),
        point({
          day: "2026-08-17",
          provider_input_tokens: null,
          provider_output_tokens: null,
        }),
      ],
      "tokens",
    );
    expect(screen.getByText("2026-08-16: 30, 2026-08-17: unavailable")).toBeInTheDocument();
  });

  it("shows Unavailable when every value is null", () => {
    renderSparkline([point({ provider_input_tokens: null, provider_output_tokens: null })], "tokens");
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("line-chart")).not.toBeInTheDocument();
  });

  it("keeps a real zero distinct from an unavailable point", () => {
    renderSparkline(
      [point({ attributed_call_duration_seconds: 0 })],
      "duration",
    );
    expect(screen.getByText("2026-08-17: 0")).toBeInTheDocument();
  });
});
