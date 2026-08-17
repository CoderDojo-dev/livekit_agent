import { describe, expect, it } from "vitest";
import { duration, money, quantity } from "./format";

describe("format", () => {
  it("renders TND and never a bare number", () => {
    expect(money(12.5)).toContain("TND");
    expect(money(null)).toBe("—");
  });
  it("renders units without pretending they are currency", () => {
    expect(quantity(2.5, "GB")).toBe("2.5 GB");
    expect(quantity(120, "MIN")).toBe("120 MIN");
    expect(quantity(4, "TND")).toContain("TND");
  });
  it("formats real durations", () => {
    expect(duration(258)).toBe("4m 18s"); // the value that used to be hardcoded
    expect(duration(42)).toBe("42s");
    expect(duration(null)).toBe("—");
  });
});
