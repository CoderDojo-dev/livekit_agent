import { describe, expect, it } from "vitest";
import { LOCALES, LOCALE_LABEL, LOCALE_SHORT, isRtl, translate, type Locale } from "./i18n";
import { NAV, PAGE_HEAD } from "./nav";

/*
 * The type system already guarantees that a dictionary cannot hold a key English does not have,
 * and that `labelKey` / `titleKey` are real keys. What it cannot catch is an EMPTY translation:
 * `""` type-checks perfectly and renders as a blank navigation row. Everything below is about
 * that class of mistake, plus the two shell contracts a locale can silently break.
 */

describe("the three locales", () => {
  it("offers exactly English, French and Arabic", () => {
    expect([...LOCALES]).toEqual(["en", "fr", "ar"]);
  });

  it("labels each language in its own script, which is the point of the control", () => {
    expect(LOCALE_LABEL.en).toBe("English");
    expect(LOCALE_LABEL.fr).toBe("Français");
    // A speaker who cannot read the interface has to be able to recognise their own row.
    expect(LOCALE_LABEL.ar).toBe("العربية");
    for (const locale of LOCALES) {
      expect(LOCALE_SHORT[locale].length).toBeGreaterThan(0);
    }
  });

  it("mirrors the layout for Arabic and only for Arabic", () => {
    expect(isRtl("ar")).toBe(true);
    expect(isRtl("en")).toBe(false);
    expect(isRtl("fr")).toBe(false);
  });
});

describe("navigation is fully translated", () => {
  const items = NAV.flatMap((group) => group.items);

  it("still declares the ten destinations", () => {
    expect(items).toHaveLength(10);
  });

  for (const locale of LOCALES) {
    it(`names every section and destination in ${locale}`, () => {
      for (const group of NAV) {
        expect(translate(locale, group.sectionKey).trim()).not.toBe("");
      }
      for (const item of items) {
        expect(translate(locale, item.labelKey).trim()).not.toBe("");
      }
    });
  }

  it("keeps the English dictionary and the inline label in step", () => {
    // `label` is the file's own readable copy of the English string. If the two drift, the rail
    // says one thing and a reader of nav.ts believes another.
    for (const item of items) {
      expect(translate("en", item.labelKey)).toBe(item.label);
    }
  });
});

describe("page heads are fully translated", () => {
  const routes = Object.keys(PAGE_HEAD);

  it("covers every navigation destination", () => {
    const hrefs = NAV.flatMap((group) => group.items)
      .map((item) => item.href)
      .sort();
    expect(routes.slice().sort()).toEqual(hrefs);
  });

  for (const locale of LOCALES) {
    it(`titles every page in ${locale}`, () => {
      for (const route of routes) {
        const head = PAGE_HEAD[route]!;
        expect(translate(locale, head.titleKey).trim()).not.toBe("");
        // A null subtitle is a deliberate "this page has none" (only /assistant). A key that
        // resolves to an empty string is a missing translation wearing the same clothes.
        if (head.subtitleKey !== null) {
          expect(translate(locale, head.subtitleKey).trim()).not.toBe("");
        }
      }
    });
  }

  it("gives only the assistant scene no subtitle", () => {
    const withoutSubtitle = routes.filter((route) => PAGE_HEAD[route]!.subtitleKey === null);
    expect(withoutSubtitle).toEqual(["/assistant"]);
  });
});

describe("translate()", () => {
  it("falls back to English per key, never to a raw key", () => {
    // "shell.secure" exists in all three; a key only English defines must still resolve.
    for (const locale of LOCALES) {
      const value = translate(locale, "common.loading");
      expect(value.trim()).not.toBe("");
      expect(value).not.toContain("common.");
    }
  });

  it("returns the English string for an unknown locale rather than throwing", () => {
    // Storage is user-writable; `coerce()` in preferences.ts is the guard, but translate() is
    // reached with whatever it is handed and must not be the thing that breaks the page.
    const rogue = "tlh" as Locale;
    expect(translate(rogue, "nav.billing")).toBe("Billing");
  });
});
