import { describe, expect, it } from "vitest";
import { toOrbState } from "./orb-state";
import type { AgentState } from "@livekit/components-react";

describe("toOrbState", () => {
  it("maps every LiveKit agent state to a distinct orb state", () => {
    const pairs: Array<[AgentState, string]> = [
      ["disconnected", "disconnected"],
      ["connecting", "connecting"],
      ["pre-connect-buffering", "preConnect"],
      ["initializing", "initializing"],
      ["idle", "idle"],
      ["listening", "listening"],
      ["thinking", "thinking"],
      ["speaking", "speaking"],
      ["failed", "failed"],
    ];
    for (const [agentState, orbState] of pairs) {
      expect(toOrbState(agentState, true)).toBe(orbState);
    }
    // Nine in, nine distinct out: the orb has no unreachable state.
    expect(new Set(pairs.map(([, orb]) => orb)).size).toBe(9);
  });

  it("never freezes on an unknown state", () => {
    expect(toOrbState(undefined, false)).toBe("disconnected");
    expect(toOrbState(undefined, true)).toBe("idle");
    expect(toOrbState("something-new" as AgentState, true)).toBe("idle");
  });
});
