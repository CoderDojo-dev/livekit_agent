import { describe, expect, it } from "vitest";

import { formatPhone } from "./format";

/**
 * Regression cover for the bug this function replaced.
 *
 * `maskPhone` assumed the stored number contained spaces. It does not — the CRM stores E.164
 * ("+21626078277") — so `indexOf(" ")` returned -1, `slice(0, -1)` dropped a single trailing
 * character instead of taking a 3-character head, and the UI rendered the entire number followed
 * by dots followed by a repeat of its own last four digits.
 */
describe("formatPhone", () => {
  it("splits the country code from the subscriber number", () => {
    expect(formatPhone("+21626078277")).toBe("+216 26 078 277");
  });

  it("does not emit the whole number followed by its own tail (the old defect)", () => {
    const rendered = formatPhone("+21626078277");
    expect(rendered).not.toContain("···");
    expect(rendered).not.toMatch(/2607827\s*·/);
  });

  it("is idempotent, so an already-formatted value survives a re-render", () => {
    expect(formatPhone(formatPhone("+21626078277"))).toBe("+216 26 078 277");
  });

  it("accepts the 00 international prefix", () => {
    expect(formatPhone("0021626078277")).toBe("+216 26 078 277");
  });

  it("groups a 10-digit subscriber 3-3-4 rather than stranding a leading digit", () => {
    expect(formatPhone("+15551234567")).toBe("+1 555 123 4567");
  });

  it("merges a leading orphan digit instead of leaving it alone against the country code", () => {
    // 9 subscriber digits would otherwise chunk as 1 + 3 + 3 + ... leaving a lone digit.
    expect(formatPhone("+33612345678")).not.toMatch(/^\+33 \d /);
  });

  it("formats a local number with no country code", () => {
    expect(formatPhone("26078277")).toBe("26 078 277");
  });

  it("returns short or unparseable input untouched rather than mangling it", () => {
    expect(formatPhone("+1234")).toBe("+1234");
    expect(formatPhone("  ")).toBe("");
    expect(formatPhone("")).toBe("");
  });

  it("never loses a digit", () => {
    const source = "+21626078277";
    const digitsIn = source.replace(/\D/g, "");
    const digitsOut = formatPhone(source).replace(/\D/g, "");
    expect(digitsOut).toBe(digitsIn);
  });
});
