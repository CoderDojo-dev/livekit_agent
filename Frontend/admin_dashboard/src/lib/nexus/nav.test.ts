import { describe, expect, it } from "vitest";
import { NAV, canSeeNavItem } from "./nav";

const supervisor = {
  role: "superviseur",
} as const;

const administrator = {
  role: "administrateur",
} as const;

describe("audit navigation", () => {
  it("defines exactly one canonical audit destination", () => {
    const auditItems = NAV.filter((item) => item.href === "/audit");
    expect(auditItems).toHaveLength(1);
    expect(auditItems[0]).toMatchObject({
      id: "audit",
      label: "Audit",
      minimumRole: "administrateur",
    });
  });

  it("hides Audit without an administrator session", () => {
    const audit = NAV.find((item) => item.href === "/audit");
    expect(audit).toBeDefined();
    expect(canSeeNavItem(audit!, null)).toBe(false);
    expect(canSeeNavItem(audit!, supervisor)).toBe(false);
  });

  it("shows Audit to administrators", () => {
    const audit = NAV.find((item) => item.href === "/audit");
    expect(audit).toBeDefined();
    expect(canSeeNavItem(audit!, administrator)).toBe(true);
  });

  it("keeps Settings available to authenticated lower roles", () => {
    const settings = NAV.find((item) => item.href === "/settings");
    expect(settings).toBeDefined();
    expect(settings?.minimumRole).toBeUndefined();
    expect(canSeeNavItem(settings!, supervisor)).toBe(true);
  });
});
