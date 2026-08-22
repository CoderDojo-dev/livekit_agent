import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_PREFERENCES,
  PREFERENCES_BOOT_SCRIPT,
  PREFERENCES_KEY,
  applyPreferences,
  readPreferences,
  writePreferences,
  type PortalPreferences,
} from "./preferences";

const LEGACY_KEY = "nexus_portal_preferences";

type Dataset = Record<string, string>;

/**
 * What <html> looks like after either code path has run.
 *
 * The fake used to be `{ dataset }` alone, which was enough while every setting was a
 * data-attribute. The interface language is not: it lands on `lang`, on `dir` and on
 * `style.colorScheme`, and a fake missing those three made `applyPreferences` throw rather than
 * fail an assertion. The shape below mirrors the real element for exactly the properties this
 * module writes, and the comparison covers all of them.
 */
type Root = { dataset: Dataset; lang: string; dir: string; colorScheme: string };

function fakeStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
    clear: () => map.clear(),
  };
}

let storage: ReturnType<typeof fakeStorage>;
let root: { dataset: Dataset; lang: string; dir: string; style: { colorScheme: string } };

function freshRoot() {
  root = { dataset: {}, lang: "", dir: "", style: { colorScheme: "" } };
  Object.assign(globalThis, { document: { documentElement: root } });
  return root;
}

function snapshot(): Root {
  return {
    dataset: root.dataset,
    lang: root.lang,
    dir: root.dir,
    colorScheme: root.style.colorScheme,
  };
}

beforeEach(() => {
  storage = fakeStorage();
  freshRoot();
  Object.assign(globalThis, {
    window: { localStorage: storage },
    localStorage: storage,
  });
});

afterEach(() => {
  Reflect.deleteProperty(globalThis, "window");
  Reflect.deleteProperty(globalThis, "localStorage");
  Reflect.deleteProperty(globalThis, "document");
});

/** What the head script leaves on <html>, for a given stored payload. */
function bootDataset(raw: string | null): Root {
  if (raw !== null) storage.setItem(PREFERENCES_KEY, raw);
  freshRoot();
  new Function(PREFERENCES_BOOT_SCRIPT)();
  return snapshot();
}

/** What the running app would leave on <html>, for the same payload. */
function runtimeDataset(raw: string | null): Root {
  storage.clear();
  if (raw !== null) storage.setItem(PREFERENCES_KEY, raw);
  freshRoot();
  applyPreferences(readPreferences());
  return snapshot();
}

describe("readPreferences", () => {
  it("returns the defaults when nothing is stored", () => {
    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES);
  });

  it("merges a partial payload over the defaults", () => {
    storage.setItem(PREFERENCES_KEY, JSON.stringify({ density: "compact" }));
    expect(readPreferences()).toEqual({ ...DEFAULT_PREFERENCES, density: "compact" });
  });

  it("falls back to the defaults on unparseable JSON", () => {
    storage.setItem(PREFERENCES_KEY, "{not json");
    expect(readPreferences()).toEqual(DEFAULT_PREFERENCES);
  });

  it("still reads the pre-rebrand key", () => {
    storage.setItem(LEGACY_KEY, JSON.stringify({ theme: "light" }));
    expect(readPreferences().theme).toBe("light");
  });
});

describe("applyPreferences", () => {
  it("carries every setting onto the document, not just the theme", () => {
    const all: PortalPreferences = {
      theme: "light",
      reduceMotion: true,
      density: "compact",
      textSize: "large",
      captions: false,
      locale: "ar",
    };
    applyPreferences(all);
    expect(root.dataset).toEqual({
      theme: "light",
      reduceMotion: "true",
      density: "compact",
      textSize: "large",
      captions: "false",
    });
    // The language is not a data-attribute: it is the document's own lang/dir, which is what the
    // CSS logical properties and the screen reader actually read.
    expect(root.lang).toBe("ar");
    expect(root.dir).toBe("rtl");
    expect(root.style.colorScheme).toBe("light");
  });

  it("is reached by a write, so a change lands on the document", () => {
    writePreferences({ ...DEFAULT_PREFERENCES, textSize: "large" });
    expect(root.dataset["textSize"]).toBe("large");
    expect(storage.getItem(PREFERENCES_KEY)).toContain('"textSize":"large"');
  });
});

describe("the pre-paint head script", () => {
  /*
   * The script is a duplicate implementation of applyPreferences written in
   * ES5 for the <head>. Anything it forgets is a setting that silently
   * reverts on reload, which is exactly the bug this suite exists to catch.
   */
  const payloads: (string | null)[] = [
    null,
    "{}",
    "not json at all",
    "null",
    '"a string"',
    JSON.stringify({ theme: "light" }),
    JSON.stringify({ density: "compact", textSize: "large" }),
    JSON.stringify({ reduceMotion: true, captions: false }),
    JSON.stringify({
      theme: "light",
      reduceMotion: true,
      density: "compact",
      textSize: "large",
      captions: false,
    }),
    JSON.stringify({ theme: "chartreuse", density: "roomy", textSize: 42 }),
    // The interface language, through the boot script and the runtime alike.
    JSON.stringify({ locale: "fr" }),
    JSON.stringify({ locale: "ar" }),
    JSON.stringify({ locale: "en", theme: "light" }),
    // Storage is user-writable: an unknown locale must land on English, not on <html lang="tlh">.
    JSON.stringify({ locale: "tlh" }),
    JSON.stringify({ locale: 7 }),
  ];

  for (const raw of payloads) {
    it(`agrees with applyPreferences for ${raw ?? "an empty store"}`, () => {
      expect(bootDataset(raw)).toEqual(runtimeDataset(raw));
    });
  }

  it("writes all five attributes even with an empty store", () => {
    expect(Object.keys(bootDataset(null).dataset).sort()).toEqual([
      "captions",
      "density",
      "reduceMotion",
      "textSize",
      "theme",
    ]);
  });

  /*
   * Direction is the one setting that CANNOT wait for the bundle: applying dir from React would
   * paint one frame of a left-to-right Arabic page and then flip the entire layout. These two
   * assert the head script gets there first.
   */
  it("sets lang and ltr before paint for a Latin locale", () => {
    const booted = bootDataset(JSON.stringify({ locale: "fr" }));
    expect(booted.lang).toBe("fr");
    expect(booted.dir).toBe("ltr");
  });

  it("sets lang and rtl before paint for Arabic", () => {
    const booted = bootDataset(JSON.stringify({ locale: "ar" }));
    expect(booted.lang).toBe("ar");
    expect(booted.dir).toBe("rtl");
  });

  it("falls back to English for a locale that is not one of the three", () => {
    expect(bootDataset(JSON.stringify({ locale: "tlh" })).lang).toBe("en");
    expect(runtimeDataset(JSON.stringify({ locale: "tlh" })).lang).toBe("en");
  });
});
