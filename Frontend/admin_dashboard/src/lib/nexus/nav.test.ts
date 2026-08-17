import { describe, expect, it } from "vitest";
import { NAV, canSeeNavItem } from "./nav";

const audit = NAV.find((item) => item.href === "/audit")!;

describe("audit navigation RBAC", () => {
  it("is a single administrator-only destination", () => {
    expect(NAV.filter((item) => item.href === "/audit")).toHaveLength(1);
    expect(audit.minimumRole).toBe("administrateur");
  });
  it("is hidden below administrator rank", () => {
    expect(canSeeNavItem(audit, null)).toBe(false);
    expect(canSeeNavItem(audit, { role: "superviseur" })).toBe(false);
    expect(canSeeNavItem(audit, { role: "administrateur" })).toBe(true);
  });
});
