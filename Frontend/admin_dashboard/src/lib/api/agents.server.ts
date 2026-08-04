import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type AgentActivityRow = {
  agent: string;
  turns: number;
  sessions: number;
  last_seen: string | null;
};

export type AgentActivity = {
  window_days: number;
  total_turns: number;
  total_sessions: number;
  agents: AgentActivityRow[];
};

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
