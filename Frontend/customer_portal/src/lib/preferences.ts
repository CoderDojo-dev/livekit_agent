/**
 * lib/preferences.ts — presentation settings only.
 *
 * Nothing here is sent to a server, because no preferences table exists in
 * version_92 and inventing one would change backend behaviour. Every value is
 * a pure rendering choice applied as a data-attribute on <html>.
 *
 * The module is also the store: components read through usePreferences() so a
 * change made on the preferences screen reaches the shell, the assistant and
 * every other mounted surface without a reload.
 */
import { useSyncExternalStore } from "react";

export type Density = "comfortable" | "compact";
export type TextSize = "default" | "large";
export type PortalTheme = "dark" | "light";
/**
 * Duplicated rather than imported from i18n.ts: that module imports THIS one for the store, and a
 * cycle here would break the pre-paint script's key list. i18n.ts re-exports the same union as
 * `Locale`, and the two are kept in step by the `pick()` call in coerce() below.
 */
export type PortalLocale = "en" | "fr" | "ar";

export type PortalPreferences = {
  theme: PortalTheme;
  reduceMotion: boolean;
  density: Density;
  textSize: TextSize;
  captions: boolean;
  /**
   * INTERFACE language. Presentation only: it never reaches a server, and it is NOT the language
   * the assistant speaks — that is crm.customers.preferred_language, set through
   * me.server.setPreferredLanguage and read by the agent-worker at session start. Arabic also
   * flips the document to RTL.
   */
  locale: PortalLocale;
};

export const DEFAULT_PREFERENCES: PortalPreferences = {
  theme: "dark",
  reduceMotion: false,
  density: "comfortable",
  textSize: "default",
  captions: true,
  locale: "en",
};

export const PREFERENCES_KEY = "portal_preferences";
// Written by the pre-rebrand release. Read so existing settings survive the
// key rename; writes go to PREFERENCES_KEY only and the legacy entry ages out.
const LEGACY_KEY = "nexus_portal_preferences";

/*
 * Storage is user-writable and survives deploys, so a value can be anything:
 * a stale enum from an older release, a hand-edited string, a whole different
 * shape. Every field is validated rather than spread, because an unrecognised
 * theme reaches <html data-theme="..."> and matches no stylesheet rule at all.
 */
function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function coerce(raw: string | null): PortalPreferences {
  if (!raw) return DEFAULT_PREFERENCES;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return DEFAULT_PREFERENCES;
  }
  if (typeof parsed !== "object" || parsed === null) return DEFAULT_PREFERENCES;
  const stored = parsed as Partial<Record<keyof PortalPreferences, unknown>>;
  return {
    theme: pick(stored.theme, ["dark", "light"] as const, DEFAULT_PREFERENCES.theme),
    reduceMotion:
      typeof stored.reduceMotion === "boolean"
        ? stored.reduceMotion
        : DEFAULT_PREFERENCES.reduceMotion,
    density: pick(stored.density, ["comfortable", "compact"] as const, DEFAULT_PREFERENCES.density),
    textSize: pick(stored.textSize, ["default", "large"] as const, DEFAULT_PREFERENCES.textSize),
    captions: typeof stored.captions === "boolean" ? stored.captions : DEFAULT_PREFERENCES.captions,
    locale: pick(stored.locale, ["en", "fr", "ar"] as const, DEFAULT_PREFERENCES.locale),
  };
}

export function readPreferences(): PortalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    return coerce(
      window.localStorage.getItem(PREFERENCES_KEY) ?? window.localStorage.getItem(LEGACY_KEY),
    );
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: PortalPreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
  } catch {
    /* storage disabled — the session-scoped value still applies */
  }
  applyPreferences(next);
}

/** Single place that touches the document. Attributes only, never inline styles. */
export function applyPreferences(next: PortalPreferences): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset["theme"] = next.theme;
  root.dataset["reduceMotion"] = String(next.reduceMotion);
  root.dataset["density"] = next.density;
  root.dataset["textSize"] = next.textSize;
  root.dataset["captions"] = String(next.captions);
  // `lang` drives hyphenation, quotation marks and screen-reader pronunciation; `dir` mirrors the
  // whole layout through the CSS logical properties the shell is built on.
  root.lang = next.locale;
  root.dir = next.locale === "ar" ? "rtl" : "ltr";
  // colorScheme drives the native form controls, the scrollbar and the OS focus ring.
  root.style.colorScheme = next.theme;
}

/*
 * The blocking <head> script. It has to be a string of plain ES5 because it
 * runs before the bundle, and it has to mirror applyPreferences exactly:
 * whatever it fails to set is a setting that silently reverts on reload.
 */
export const PREFERENCES_BOOT_SCRIPT = [
  "(function(){var d=document.documentElement,p=null;",
  // Read and parse in their own try: a corrupted entry must fall through to
  // the defaults, not abort the whole script and leave <html> bare.
  "try{var r=localStorage.getItem(" + JSON.stringify(PREFERENCES_KEY) + ")||",
  "localStorage.getItem(" + JSON.stringify(LEGACY_KEY) + ");if(r){p=JSON.parse(r);}}catch(e){}",
  'if(!p||typeof p!=="object"){p={};}',
  'try{d.dataset.theme=p.theme==="light"?"light":"dark";',
  'd.dataset.reduceMotion=p.reduceMotion===true?"true":"false";',
  'd.dataset.density=p.density==="compact"?"compact":"comfortable";',
  'd.dataset.textSize=p.textSize==="large"?"large":"default";',
  'd.dataset.captions=p.captions===false?"false":"true";',
  // Language and direction have to be set BEFORE first paint like everything else here: applying
  // dir from the bundle would render one frame of a left-to-right Arabic page and then flip it.
  'var l=p.locale;if(l!=="fr"&&l!=="ar"){l="en";}d.lang=l;d.dir=l==="ar"?"rtl":"ltr";',
  'd.style.colorScheme=p.theme==="light"?"light":"dark";}catch(e){}})();',
].join("");

/* -------------------------------------------------------------------------- *
 * Store. useSyncExternalStore rather than useState: the server render has no
 * localStorage, so a lazy useState initialiser hydrates from the wrong value
 * and the toggles render out of sync with the document.
 * -------------------------------------------------------------------------- */
let cache: PortalPreferences | null = null;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function clientSnapshot(): PortalPreferences {
  if (cache === null) cache = readPreferences();
  return cache;
}

function serverSnapshot(): PortalPreferences {
  return DEFAULT_PREFERENCES;
}

function onStorage(event: StorageEvent): void {
  if (event.key !== null && event.key !== PREFERENCES_KEY) return;
  cache = readPreferences();
  applyPreferences(cache);
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

/** Reactive read. Returns the defaults during SSR and the stored values after. */
export function usePreferences(): PortalPreferences {
  return useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
}

/** Merge, persist, apply to the document, and wake every subscriber. */
export function updatePreferences(patch: Partial<PortalPreferences>): PortalPreferences {
  const next = { ...clientSnapshot(), ...patch };
  cache = next;
  writePreferences(next);
  notify();
  return next;
}

/** Re-read storage into the store. Used once on mount as the boot fallback. */
export function syncPreferences(): void {
  const next = readPreferences();
  cache = next;
  applyPreferences(next);
  notify();
}
