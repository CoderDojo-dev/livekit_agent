import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type AgentActivityRow = {
  agent: string; sessions: number; duration_seconds: number; average_duration_seconds: number | null;
  last_seen: string | null; input_tokens: number | null; output_tokens: number | null; total_tokens: number | null;
  token_sessions: number; coverage: "available" | "partial" | "unavailable";
  daily: Array<{ day: string; duration_seconds: number }>;
};
export type AgentActivity = { window_days: number; total_sessions: number; total_duration_seconds: number; input_tokens: number | null; output_tokens: number | null; token_history: "forward_only_no_backfill"; agents: AgentActivityRow[]; };

export const getAgentActivity = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { days?: unknown };
    const days = Number(input.days);
    return {
      days: Number.isInteger(days) && days >= 1 && days <= 365 ? days : 30,
    };
  })
  .handler(async ({ data, context }) =>
    businessApi<AgentActivity>("/api/v1/agents/activity", {
      method: "GET",
      query: { days: data.days },
      role: context.session.role,
    }),
  );
