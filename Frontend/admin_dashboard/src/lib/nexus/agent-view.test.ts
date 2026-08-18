import { describe, expect, it } from "vitest";
import type {
  AgentActivityPersona,
  AgentDailyPoint,
} from "@/lib/api/agents.server";
import {
  agentLabel,
  dailyTokenTotal,
  formatDuration,
  formatLastSeen,
  humanizeClassName,
  isKnownAgent,
  mergeAgentRows,
  providerTokenTotal,
  sharePercent,
} from "@/lib/nexus/agent-view";

const WINDOW = { from: "2026-08-11T00:00:00.000Z", days: 7 };

const DAY_KEYS = [
  "2026-08-11",
  "2026-08-12",
  "2026-08-13",
  "2026-08-14",
  "2026-08-15",
  "2026-08-16",
  "2026-08-17",
];

function day(overrides: Partial<AgentDailyPoint>): AgentDailyPoint {
  return {
    day: "2026-08-17",
    attributed_calls: 1,
    attributed_call_duration_seconds: 120,
    provider_input_tokens: 10,
    provider_output_tokens: 20,
    ...overrides,
  };
}

function persona(overrides: Partial<AgentActivityPersona>): AgentActivityPersona {
  return {
    persona: "BillingAgent",
    attributed_calls: 5,
    completed_calls: 4,
    attributed_call_duration_seconds: 1200,
    average_completed_call_duration_seconds: 300,
    last_observed_at: "2026-08-17T10:00:00.000Z",
    provider_input_tokens: 50,
    provider_output_tokens: 60,
    token_event_count: 2,
    daily: [day({})],
    ...overrides,
  };
}

describe("mergeAgentRows", () => {
  it("unions the static catalog with observed personas", () => {
    const rows = mergeAgentRows([persona({})], 5, WINDOW);
    expect(rows.map((row) => row.className).sort()).toEqual([
      "AccountServicesAgent",
      "BillingAgent",
      "ManagerAgent",
      "TechnicalAgent",
      "TriageAgent",
    ]);
    const billing = rows.find((row) => row.className === "BillingAgent")!;
    expect(billing.attributedCalls).toBe(5);
    expect(billing.label).toBe("Billing");
  });

  it("keeps an unobserved catalog persona as an idle row", () => {
    const rows = mergeAgentRows([persona({})], 5, WINDOW);
    const triage = rows.find((row) => row.className === "TriageAgent")!;
    expect(triage.attributedCalls).toBe(0);
    expect(triage.completedCalls).toBe(0);
    expect(triage.attributedCallDurationSeconds).toBe(0);
    expect(triage.lastObservedAt).toBeNull();
    expect(triage.daily.map((point) => point.day)).toEqual(DAY_KEYS);
    expect(triage.daily.every((point) => point.attributed_calls === 0)).toBe(true);
  });

  it("surfaces an unknown persona with a humanized label", () => {
    const rows = mergeAgentRows(
      [persona({ persona: "OdrAgent" })],
      5,
      WINDOW,
    );
    const row = rows.find((entry) => entry.className === "OdrAgent")!;
    expect(row.catalog).toBeNull();
    expect(row.label).toBe("Odr");
    expect(isKnownAgent("OdrAgent")).toBe(false);
    expect(agentLabel("OdrAgent")).toBe("Odr");
  });

  it("keeps a token-only persona with zero attributed calls", () => {
    const rows = mergeAgentRows(
      [persona({ persona: "TechnicalAgent", attributed_calls: 0, daily: [] })],
      0,
      WINDOW,
    );
    const technical = rows.find((row) => row.className === "TechnicalAgent")!;
    expect(technical.attributedCalls).toBe(0);
    expect(technical.providerInputTokens).toBe(50);
    expect(technical.providerOutputTokens).toBe(60);
  });

  it("preserves the observed persona's backend-provided daily points", () => {
    const rows = mergeAgentRows([persona({})], 5, WINDOW);
    const billing = rows.find((row) => row.className === "BillingAgent")!;
    expect(billing.daily.map((point) => point.day)).toEqual(["2026-08-17"]);
    expect(billing.daily[0]!.attributed_calls).toBe(1);
  });

  it("preserves null token fields instead of inventing zeros", () => {
    const rows = mergeAgentRows(
      [persona({ provider_input_tokens: null, provider_output_tokens: null })],
      5,
      WINDOW,
    );
    const billing = rows.find((row) => row.className === "BillingAgent")!;
    expect(billing.providerInputTokens).toBeNull();
    expect(billing.providerOutputTokens).toBeNull();
  });

  it("computes the attribution share against the global attribution count", () => {
    const rows = mergeAgentRows(
      [
        persona({ persona: "TriageAgent", attributed_calls: 4 }),
        persona({ persona: "BillingAgent", attributed_calls: 6 }),
      ],
      10,
      WINDOW,
    );
    const triage = rows.find((row) => row.className === "TriageAgent")!;
    const billing = rows.find((row) => row.className === "BillingAgent")!;
    expect(triage.attributionShare).toBeCloseTo(0.4);
    expect(billing.attributionShare).toBeCloseTo(0.6);
  });

  it("sorts by attributed calls, then by attributed duration", () => {
    const rows = mergeAgentRows(
      [
        persona({
          persona: "TriageAgent",
          attributed_calls: 2,
          attributed_call_duration_seconds: 60,
        }),
        persona({
          persona: "BillingAgent",
          attributed_calls: 2,
          attributed_call_duration_seconds: 600,
        }),
        persona({
          persona: "TechnicalAgent",
          attributed_calls: 5,
        }),
      ],
      9,
      WINDOW,
    );
    expect(rows.map((row) => row.className)).toEqual([
      "TechnicalAgent",
      "BillingAgent",
      "TriageAgent",
      "AccountServicesAgent",
      "ManagerAgent",
    ]);
  });
});

describe("formatDuration", () => {
  it("formats sub-minute durations in seconds", () => {
    expect(formatDuration(45)).toBe("45s");
    expect(formatDuration(59)).toBe("59s");
  });

  it("rounds minutes below one hour", () => {
    expect(formatDuration(60)).toBe("1m");
    expect(formatDuration(3599)).toBe("60m");
  });

  it("formats hours with minutes only when non-zero", () => {
    expect(formatDuration(3600)).toBe("1h");
    expect(formatDuration(3660)).toBe("1h 1m");
  });
});

describe("providerTokenTotal / dailyTokenTotal", () => {
  it("returns null when both provider scopes are null", () => {
    const rows = mergeAgentRows(
      [persona({ provider_input_tokens: null, provider_output_tokens: null })],
      5,
      WINDOW,
    );
    expect(providerTokenTotal(rows[0]!)).toBeNull();
    expect(dailyTokenTotal(day({ provider_input_tokens: null, provider_output_tokens: null }))).toBeNull();
  });

  it("sums input and output when at least one scope exists", () => {
    const rows = mergeAgentRows([persona({})], 5, WINDOW);
    expect(providerTokenTotal(rows[0]!)).toBe(110);
    const nullInput = mergeAgentRows(
      [persona({ provider_input_tokens: null })],
      5,
      WINDOW,
    );
    expect(providerTokenTotal(nullInput[0]!)).toBe(60);
    expect(dailyTokenTotal(day({ provider_input_tokens: null }))).toBe(20);
  });
});

describe("sharePercent / formatLastSeen / labels", () => {
  it("formats the attribution share", () => {
    expect(sharePercent(0.4)).toBe("40%");
    expect(sharePercent(0.004)).toBe("<1%");
    expect(sharePercent(0)).toBe("0%");
    expect(sharePercent(Number.NaN)).toBe("0%");
  });

  it("formats an ISO instant without timezone math", () => {
    expect(formatLastSeen("2026-08-17T10:04:00.000Z")).toBe("2026-08-17 10:04");
    expect(formatLastSeen(null)).toBe("\u2014");
  });

  it("labels catalog personas by catalog entry", () => {
    expect(agentLabel("AccountServicesAgent")).toBe("Account Services");
    expect(isKnownAgent("TriageAgent")).toBe(true);
  });

  it("humanizes class names absent from the catalog", () => {
    expect(humanizeClassName("OdrAgent")).toBe("Odr");
    expect(humanizeClassName("ProvisioningAgent")).toBe("Provisioning");
  });
});
