import { describe, expect, it } from "vitest";
import { parseToolEvent, timestampMs, toolEventText } from "./tool-events";

const valid = {
  version: 1,
  kind: "tool",
  id: "call_1",
  name: "get_balance_summary",
  label: "Reading Balance Information",
  status: "done",
  created_at: 1_700_000_000,
};

describe("parseToolEvent", () => {
  it("accepts the exact frontend_events.py payload", () => {
    expect(parseToolEvent(JSON.stringify(valid))?.name).toBe("get_balance_summary");
  });

  it("rejects anything else without throwing", () => {
    for (const bad of [
      "not json",
      "{}",
      JSON.stringify({ ...valid, version: 2 }),
      JSON.stringify({ ...valid, kind: "persona" }),
      JSON.stringify({ ...valid, status: "running" }),
    ]) {
      expect(parseToolEvent(bad)).toBeNull();
    }
  });
});

describe("toolEventText", () => {
  it("never leaks a tool name", () => {
    const names = [
      "knowledge_search",
      "get_invoice_summary",
      "get_balance_summary",
      "get_plan_details",
      "route_to_billing",
      "route_to_technical",
      "escalate_to_manager",
      "verify_with_known_element",
      "record_consent",
      "change_plan",
      "execute_payment",
      "unblock_sim",
      "replace_sim",
      "create_ticket",
      "schedule_callback",
    ];
    for (const name of names) {
      for (const status of ["done", "error"] as const) {
        const text = toolEventText({ ...valid, name, status } as never);
        expect(text).not.toContain("_");
        expect(text.length).toBeGreaterThan(3);
      }
    }
  });

  it("falls back to the worker label, then to generic copy", () => {
    expect(toolEventText({ ...valid, name: "brand_new_tool" } as never)).toBe(
      "Reading Balance Information",
    );
    expect(
      toolEventText({ ...valid, name: "brand_new_tool", label: "Service action" } as never),
    ).toBeTruthy();
  });
});

describe("timestampMs", () => {
  it("normalises seconds and milliseconds", () => {
    expect(timestampMs(1_700_000_000)).toBe(1_700_000_000_000);
    expect(timestampMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
});
