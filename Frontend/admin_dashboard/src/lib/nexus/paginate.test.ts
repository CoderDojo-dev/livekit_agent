import { describe, expect, it } from "vitest";

import { clampPage, offsetFor, pageCount, pageTokens, rangeFor, slicePage } from "./paginate";

/**
 * These functions replaced three different ad-hoc paging affordances ("Load more", "Load older",
 * a bare Previous/Next pair) across ten pages. The edge cases below are the ones that actually
 * bit the old implementations: empty sets, a filter shrinking the set under the current page,
 * and a final page that is not full.
 */

describe("pageCount", () => {
  it("never reports zero pages, so the pager cannot render 'page 1 of 0'", () => {
    expect(pageCount(0, 10)).toBe(1);
  });

  it("rounds a partial last page up", () => {
    expect(pageCount(21, 10)).toBe(3);
    expect(pageCount(20, 10)).toBe(2);
  });

  it("survives a nonsensical page size instead of dividing by zero", () => {
    expect(pageCount(50, 0)).toBe(1);
    expect(pageCount(50, -5)).toBe(1);
  });
});

describe("clampPage", () => {
  it("pulls a stranded page back into range when a filter shrinks the set", () => {
    // Was on page 9 of 10; a filter cuts the set to 12 rows (2 pages).
    expect(clampPage(9, 12, 10)).toBe(1);
  });

  it("refuses negative pages", () => {
    expect(clampPage(-3, 100, 10)).toBe(0);
  });

  it("leaves a valid page untouched", () => {
    expect(clampPage(4, 100, 10)).toBe(4);
  });
});

describe("offsetFor", () => {
  it("maps a zero-based page onto a row offset", () => {
    expect(offsetFor(0, 25)).toBe(0);
    expect(offsetFor(3, 25)).toBe(75);
  });

  it("never emits a negative offset, which the backend would reject", () => {
    expect(offsetFor(-2, 25)).toBe(0);
  });
});

describe("slicePage", () => {
  const rows = Array.from({ length: 23 }, (_, index) => index);

  it("cuts a full window", () => {
    expect(slicePage(rows, 1, 10)).toEqual([10, 11, 12, 13, 14, 15, 16, 17, 18, 19]);
  });

  it("returns the short remainder on the last page", () => {
    expect(slicePage(rows, 2, 10)).toEqual([20, 21, 22]);
  });

  it("clamps rather than returning an empty array for an out-of-range page", () => {
    expect(slicePage(rows, 99, 10)).toEqual([20, 21, 22]);
  });

  it("handles an empty set", () => {
    expect(slicePage([], 0, 10)).toEqual([]);
  });
});

describe("rangeFor", () => {
  it("is 1-based and inclusive, matching the footer readout", () => {
    expect(rangeFor(0, 10, 95)).toEqual({ from: 1, to: 10 });
    expect(rangeFor(1, 10, 95)).toEqual({ from: 11, to: 20 });
  });

  it("stops at the total on a partial last page", () => {
    expect(rangeFor(9, 10, 95)).toEqual({ from: 91, to: 95 });
  });

  it("collapses to zero for an empty set so the caller can say 'No rows'", () => {
    expect(rangeFor(0, 10, 0)).toEqual({ from: 0, to: 0 });
  });
});

describe("pageTokens", () => {
  it("lists every page when the set is short enough to need no elision", () => {
    expect(pageTokens(0, 5)).toEqual([
      { kind: "page", page: 0 },
      { kind: "page", page: 1 },
      { kind: "page", page: 2 },
      { kind: "page", page: 3 },
      { kind: "page", page: 4 },
    ]);
  });

  it("always keeps the first and last page reachable", () => {
    const tokens = pageTokens(20, 42);
    expect(tokens[0]).toEqual({ kind: "page", page: 0 });
    expect(tokens[tokens.length - 1]).toEqual({ kind: "page", page: 41 });
  });

  it("elides only on the side that actually skips pages", () => {
    // At the start there is nothing to elide on the left.
    const atStart = pageTokens(0, 42);
    expect(atStart.some((token) => token.kind === "gap" && token.key === "head")).toBe(false);
    expect(atStart.some((token) => token.kind === "gap" && token.key === "tail")).toBe(true);

    const atEnd = pageTokens(41, 42);
    expect(atEnd.some((token) => token.kind === "gap" && token.key === "head")).toBe(true);
    expect(atEnd.some((token) => token.kind === "gap" && token.key === "tail")).toBe(false);
  });

  it("keeps a stable token count as the reader pages through, so the footer never jumps", () => {
    const widths = [5, 10, 20, 30, 36].map((page) => pageTokens(page, 42).length);
    expect(new Set(widths).size).toBe(1);
  });

  it("returns nothing for a set with no pages", () => {
    expect(pageTokens(0, 0)).toEqual([]);
  });
});
