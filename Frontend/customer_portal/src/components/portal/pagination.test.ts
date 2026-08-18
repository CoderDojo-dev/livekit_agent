import { describe, expect, it } from "vitest";
import { pageWindow } from "@/components/portal/data";

describe("pageWindow", () => {
  it("lists every page when there are few", () => {
    expect(pageWindow(1, 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("always includes first, last and current", () => {
    const out = pageWindow(6, 12);
    expect(out).toContain(1);
    expect(out).toContain(12);
    expect(out).toContain(6);
  });

  it("never renders two gaps in a row", () => {
    const out = pageWindow(6, 40).map(String);
    expect(out.join(",")).not.toContain("gap,gap");
  });

  it("stays inside the range at both ends", () => {
    for (const current of [1, 2, 39, 40]) {
      const numbers = pageWindow(current, 40).filter((p): p is number => typeof p === "number");
      expect(Math.min(...numbers)).toBeGreaterThanOrEqual(1);
      expect(Math.max(...numbers)).toBeLessThanOrEqual(40);
    }
  });
});
