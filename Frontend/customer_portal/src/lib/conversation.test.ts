import { describe, expect, it } from "vitest";
import { turnCount, turnLines } from "./conversation";
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
