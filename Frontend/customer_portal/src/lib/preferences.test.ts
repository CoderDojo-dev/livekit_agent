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
let dataset: Dataset;

beforeEach(() => {
  storage = fakeStorage();
  dataset = {};
  Object.assign(globalThis, {
    window: { localStorage: storage },
    localStorage: storage,
    document: { documentElement: { dataset } },
  });
});

afterEach(() => {
  Reflect.deleteProperty(globalThis, "window");
  Reflect.deleteProperty(globalThis, "localStorage");
  Reflect.deleteProperty(globalThis, "document");
});

/** What the head script leaves on <html>, for a given stored payload. */
function bootDataset(raw: string | null): Dataset {
  if (raw !== null) storage.setItem(PREFERENCES_KEY, raw);
  dataset = {};
  Object.assign(globalThis, { document: { documentElement: { dataset } } });
  new Function(PREFERENCES_BOOT_SCRIPT)();
  return dataset;
}

/** What the running app would leave on <html>, for the same payload. */
function runtimeDataset(raw: string | null): Dataset {
  storage.clear();
  if (raw !== null) storage.setItem(PREFERENCES_KEY, raw);
  dataset = {};
  Object.assign(globalThis, { document: { documentElement: { dataset } } });
  applyPreferences(readPreferences());
  return dataset;
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
    };
    applyPreferences(all);
    expect(dataset).toEqual({
      theme: "light",
      reduceMotion: "true",
      density: "compact",
      textSize: "large",
      captions: "false",
    });
  });

  it("is reached by a write, so a change lands on the document", () => {
    writePreferences({ ...DEFAULT_PREFERENCES, textSize: "large" });
    expect(dataset["textSize"]).toBe("large");
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
  ];

  for (const raw of payloads) {
    it(`agrees with applyPreferences for ${raw ?? "an empty store"}`, () => {
      expect(bootDataset(raw)).toEqual(runtimeDataset(raw));
    });
  }

  it("writes all five attributes even with an empty store", () => {
    expect(Object.keys(bootDataset(null)).sort()).toEqual([
      "captions",
      "density",
      "reduceMotion",
      "textSize",
      "theme",
    ]);
  });
});
