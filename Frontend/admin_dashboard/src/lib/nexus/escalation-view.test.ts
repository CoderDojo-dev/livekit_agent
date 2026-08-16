import { describe, expect, it } from "vitest";
import type { Escalation } from "@/lib/api/escalations.server";
import {
  escalationCustomerId,
  escalationCustomerName,
  escalationMatches,
  escalationStatusKey,
  isOpen,
} from "./escalation-view";

function escalation(overrides: Partial<Escalation> = {}): Escalation {
  return {
    id: "esc-1",
    session_id: "session-1",
    trigger: "customer_request",
    target: "human_advisor",
    resolution: null,
    dossier: {},
    created_at: "2026-01-02T03:04:05Z",
    customer_id: "cust-42",
    customer_name: "Ada Lovelace",
    customer_vip: false,
    ...overrides,
  };
}

describe("escalation view", () => {
  it("treats a null resolution as open", () => {
    expect(isOpen(escalation())).toBe(true);
    expect(escalationStatusKey(null)).toBe("open");
  });

  it("treats a resolved record as closed", () => {
    const row = escalation({
      resolution: "resolved",
    });

    expect(isOpen(row)).toBe(false);
    expect(escalationStatusKey(row.resolution)).toBe("resolved");
  });

  it("uses explicit unresolved identity fallbacks", () => {
    const row = escalation({
      customer_name: null,
      customer_id: null,
      customer_vip: null,
    });

    expect(escalationCustomerName(row)).toBe("Customer unresolved");
    expect(escalationCustomerId(row)).toBe("—");
  });

  it.each([
    ["ada", true],
    ["ADA", true],
    ["cust-42", true],
    ["CUST-42", true],
    ["session-1", true],
    ["customer_request", true],
    ["human_advisor", true],
    ["missing", false],
  ])("matches supported search field %s", (query, expected) => {
    expect(escalationMatches(escalation(), query)).toBe(expected);
  });

  it("normalizes surrounding whitespace", () => {
    expect(escalationMatches(escalation(), "  Ada  ")).toBe(true);
  });

  it("does not search dossier contents", () => {
    const row = escalation({
      dossier: {
        hidden_value: "private-search-value",
      },
    });

    expect(escalationMatches(row, "private-search-value")).toBe(false);
  });
});
