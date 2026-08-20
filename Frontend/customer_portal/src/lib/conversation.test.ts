import { describe, expect, it } from "vitest";
import { cadenceTicks, turnCount, turnLines } from "./conversation";
import type { ConversationTurn } from "./api/activity.server";

const turn: ConversationTurn = {
  index: 0,
  speaker: "caller",
  agent: null,
  language: "fr",
  text: "bonjour",
  at: "2026-08-19T10:00:00Z",
};

describe("turnCount", () => {
  it("counts an array of turns (detail endpoint shape)", () => {
    expect(turnCount([turn, turn, turn])).toBe(3);
  });
  it("counts a number (summary endpoint shape)", () => {
    expect(turnCount(5)).toBe(5);
  });
  it("returns 0 for missing, null, undefined or empty data", () => {
    expect(turnCount(null)).toBe(0);
    expect(turnCount(undefined)).toBe(0);
    expect(turnCount([])).toBe(0);
  });
  it("returns 0 for junk that is neither a count nor a list", () => {
    expect(turnCount("4" as unknown as number)).toBe(0);
    expect(turnCount(-3)).toBe(0);
    expect(turnCount(Number.NaN)).toBe(0);
    expect(turnCount(2.7)).toBe(2); // a fractional count is still a count, truncated
  });
});

describe("turnLines", () => {
  it("returns the transcript array from a detail payload", () => {
    expect(turnLines({ turns: [turn, turn] })).toHaveLength(2);
  });
  it("returns an empty array for a detail payload without turns", () => {
    expect(turnLines(null)).toEqual([]);
    expect(turnLines(undefined)).toEqual([]);
    expect(turnLines({} as { turns: ConversationTurn[] })).toEqual([]);
  });
});

describe("cadenceTicks", () => {
  const mk = (index: number, speaker: "caller" | "agent", at: string | null): ConversationTurn => ({
    index,
    speaker,
    agent: null,
    language: null,
    text: "x",
    at,
  });

  it("places ticks at their real time offsets when every turn is stamped", () => {
    const { ticks, timed } = cadenceTicks([
      mk(0, "caller", "2026-08-19T12:00:00Z"),
      mk(1, "agent", "2026-08-19T12:00:30Z"),
      mk(2, "caller", "2026-08-19T12:02:00Z"),
    ]);
    expect(timed).toBe(true);
    expect(ticks.map((t) => t.x)).toEqual([0, 0.25, 1]);
    expect(ticks.map((t) => t.agent)).toEqual([false, true, false]);
  });

  it("never leaves a tick outside the strip", () => {
    const { ticks } = cadenceTicks([
      mk(0, "caller", "2026-08-19T12:00:00Z"),
      mk(1, "agent", "2026-08-19T12:00:10Z"),
      mk(2, "agent", "2026-08-19T12:00:40Z"),
    ]);
    for (const tick of ticks) {
      expect(tick.x).toBeGreaterThanOrEqual(0);
      expect(tick.x).toBeLessThanOrEqual(1);
    }
  });

  it("falls back to turn order, and says so, when a timestamp is missing", () => {
    const { ticks, timed } = cadenceTicks([
      mk(0, "caller", "2026-08-19T12:00:00Z"),
      mk(1, "agent", null),
      mk(2, "caller", "2026-08-19T12:02:00Z"),
    ]);
    expect(timed).toBe(false);
    expect(ticks.map((t) => t.x)).toEqual([0, 0.5, 1]);
  });

  it("falls back to turn order for unparseable timestamps", () => {
    const { timed } = cadenceTicks([
      mk(0, "caller", "not a date"),
      mk(1, "agent", "2026-08-19T12:00:30Z"),
    ]);
    expect(timed).toBe(false);
  });

  it("treats a zero span as untimed rather than dividing by zero", () => {
    const { ticks, timed } = cadenceTicks([
      mk(0, "caller", "2026-08-19T12:00:00Z"),
      mk(1, "agent", "2026-08-19T12:00:00Z"),
    ]);
    expect(timed).toBe(false);
    expect(ticks.map((t) => t.x)).toEqual([0, 1]);
    expect(ticks.every((t) => Number.isFinite(t.x))).toBe(true);
  });

  it("treats out-of-order turns as a sequence, not a mirrored timeline", () => {
    const { timed } = cadenceTicks([
      mk(0, "caller", "2026-08-19T12:02:00Z"),
      mk(1, "agent", "2026-08-19T12:00:00Z"),
    ]);
    expect(timed).toBe(false);
  });

  it("emits one tick per turn and invents none", () => {
    const lines = Array.from({ length: 11 }, (_, i) =>
      mk(i, i % 2 === 0 ? "caller" : "agent", null),
    );
    expect(cadenceTicks(lines).ticks).toHaveLength(11);
  });

  it("returns nothing to draw for an empty transcript", () => {
    expect(cadenceTicks([])).toEqual({ ticks: [], timed: false });
  });
});
