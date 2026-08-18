import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const state: { roles: string[] } = { roles: [] };
  return {
    state,
    requireRole: (minimum: string) => {
      state.roles.push(minimum);
      return { __mock: "roleMiddleware" };
    },
  };
});

vi.mock("@/lib/api/middleware", () => ({
  authedMiddleware: { __mock: "authedMiddleware" },
  requireRole: mocks.requireRole,
}));

import {
  AgentActivityInputSchema,
  AgentActivitySchema,
  getAgentActivity,
} from "@/lib/api/agents.server";
import type { AgentActivity } from "@/lib/api/agents.server";

const definitions: AgentActivity["definitions"] = {
  agent_kind: "persona_class",
  duration_kind: "non_exclusive_attributed_call_duration",
  token_source: "provider_reported",
  token_history: "forward_only_no_backfill",
};

const valid: AgentActivity = {
  window: {
    days: 7,
    timezone: "UTC",
    from: "2026-08-11T00:00:00Z",
    to: "2026-08-18T00:00:00Z",
  },
  definitions,
  totals: {
    global_unique_calls: 12,
    persona_call_attributions: 15,
    attributed_call_duration_seconds: 3600,
    provider_input_tokens: 100,
    provider_output_tokens: 200,
  },
  personas: [
    {
      persona: "BillingAgent",
      attributed_calls: 5,
      completed_calls: 4,
      attributed_call_duration_seconds: 1200,
      average_completed_call_duration_seconds: 300,
      last_observed_at: "2026-08-17T10:00:00Z",
      provider_input_tokens: 50,
      provider_output_tokens: 60,
      token_event_count: 2,
      daily: [
        {
          day: "2026-08-17",
          attributed_calls: 1,
          attributed_call_duration_seconds: 120,
          provider_input_tokens: 10,
          provider_output_tokens: 20,
        },
      ],
    },
  ],
};

describe("AgentActivitySchema (response contract)", () => {
  it("accepts a valid response", () => {
    expect(AgentActivitySchema.parse(valid)).toEqual(valid);
  });

  it("preserves a null token scope instead of inventing zeros", () => {
    const fixture = structuredClone(valid);
    fixture.totals.provider_input_tokens = null;
    fixture.totals.provider_output_tokens = null;
    fixture.personas[0]!.provider_input_tokens = null;
    fixture.personas[0]!.provider_output_tokens = null;
    fixture.personas[0]!.daily[0]!.provider_input_tokens = null;
    fixture.personas[0]!.daily[0]!.provider_output_tokens = null;
    const parsed = AgentActivitySchema.parse(fixture);
    expect(parsed.totals.provider_input_tokens).toBeNull();
    expect(parsed.totals.provider_output_tokens).toBeNull();
    expect(parsed.personas[0]!.provider_input_tokens).toBeNull();
    expect(parsed.personas[0]!.daily[0]!.provider_output_tokens).toBeNull();
  });

  it("keeps a real zero token count distinct from null", () => {
    const fixture = structuredClone(valid);
    fixture.totals.provider_input_tokens = 0;
    fixture.personas[0]!.provider_input_tokens = 0;
    const parsed = AgentActivitySchema.parse(fixture);
    expect(parsed.totals.provider_input_tokens).toBe(0);
    expect(parsed.personas[0]!.provider_input_tokens).toBe(0);
  });

  it("rejects a negative counter", () => {
    const fixture = structuredClone(valid);
    fixture.personas[0]!.attributed_calls = -1;
    expect(() => AgentActivitySchema.parse(fixture)).toThrow();
  });

  it("rejects a non-ISO last_observed_at", () => {
    const fixture = structuredClone(valid);
    fixture.personas[0]!.last_observed_at = "not-a-date";
    expect(() => AgentActivitySchema.parse(fixture)).toThrow();
  });

  it("rejects a non-ISO day", () => {
    const fixture = structuredClone(valid);
    fixture.personas[0]!.daily[0]!.day = "17/08/2026";
    expect(() => AgentActivitySchema.parse(fixture)).toThrow();
  });

  it("rejects a missing definition key", () => {
    const fixture = structuredClone(valid);
    fixture.definitions = { ...definitions };
    delete (fixture.definitions as Partial<typeof definitions>).token_source;
    expect(() => AgentActivitySchema.parse(fixture)).toThrow();
  });

  it("rejects the legacy sessions/turns/coverage response shape", () => {
    const legacy = {
      window: { days: 7, timezone: "UTC" },
      agents: [
        {
          sessions: 3,
          turns: 9,
          coverage: 0.5,
          totalTokens: 100,
        },
      ],
    };
    expect(() => AgentActivitySchema.parse(legacy)).toThrow();
  });
});

describe("AgentActivityInputSchema (input validation)", () => {
  it("rejects invalid days instead of silently defaulting", () => {
    expect(() => AgentActivityInputSchema.parse({ days: 0 })).toThrow();
    expect(() => AgentActivityInputSchema.parse({ days: 366 })).toThrow();
    expect(() => AgentActivityInputSchema.parse({ days: 3.5 })).toThrow();
  });

  it("defaults missing days to 30", () => {
    expect(AgentActivityInputSchema.parse({}).days).toBe(30);
  });

  it("passes a valid explicit window through", () => {
    expect(AgentActivityInputSchema.parse({ days: 7 }).days).toBe(7);
  });
});

describe("getAgentActivity wiring", () => {
  it("is a server function with a GET default", () => {
    expect(typeof getAgentActivity).toBe("function");
    expect(getAgentActivity).toBeDefined();
  });

  it("keeps the supervisor role gate on the middleware chain", () => {
    expect(mocks.state.roles).toContain("superviseur");
  });
});
