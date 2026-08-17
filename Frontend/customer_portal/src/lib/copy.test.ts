import { describe, expect, it } from "vitest";
import { copy } from "./copy";
import { NAV } from "./nav";

describe("copy deck integrity", () => {
  it("covers all nine orb states", () => {
    for (const state of [
      "disconnected",
      "connecting",
      "preConnect",
      "initializing",
      "idle",
      "listening",
      "thinking",
      "speaking",
      "failed",
    ]) {
      expect(copy.assistant.state[state as keyof typeof copy.assistant.state]).toBeTruthy();
    }
  });

  it("covers all five ticket statuses (pending was missing)", () => {
    for (const status of ["open", "in_progress", "pending", "resolved", "closed"]) {
      expect(
        copy.labels.requestStatus[status as keyof typeof copy.labels.requestStatus],
      ).toBeTruthy();
    }
  });

  it("declares one nav destination per route", () => {
    const count = NAV.reduce((total, group) => total + group.items.length, 0);
    expect(count).toBe(10); // the comments used to say eleven
  });
});
