/**
 * lib/nexus/preferences.ts — presentation settings for the console.
 *
 * Ported deliberately from the customer portal's `lib/preferences.ts` rather than reinvented, so
 * the two frontends behave identically: same validation discipline, same pre-paint boot script,
 * same useSyncExternalStore store. Only the storage key and the setting list differ.
 *
 * Nothing here is sent to a server. Every value is a pure rendering choice applied as a
 * data-attribute on <html>, which is what keeps this a presentation change.
 */
import { useSyncExternalStore } from "react";

export type ConsoleTheme = "dark" | "light";
/** Duplicated rather than imported from i18n.ts: that module imports THIS one for the store, and
 *  a cycle here would break the pre-paint script's key list. i18n.ts re-exports the same union. */
export type ConsoleLocale = "en" | "fr" | "ar";
export type Density = "comfortable" | "compact";
export type TextSize = "default" | "large";

export type ConsolePreferences = {
  /** Dark is the product's native mode; light is the alternative, not the default. */
  theme: ConsoleTheme;
  /** Opt-in beyond the OS setting, for people whose OS preference is not set. */
  reduceMotion: boolean;
  /** Table row height. Compact fits roughly a third more rows on the same screen. */
  density: Density;
  textSize: TextSize;
  /** Reveals the `G O` style shortcut hints in the sidebar without hovering. */
  showShortcuts: boolean;
  /** Sidebar queue badges. Off stops the 60s poll entirely. */
  showNavCounts: boolean;
  /** Interface language. Arabic also flips the document to RTL. */
  locale: ConsoleLocale;
};

export const DEFAULT_PREFERENCES: ConsolePreferences = {
  theme: "dark",
  reduceMotion: false,
  density: "comfortable",
  textSize: "default",
  showShortcuts: false,
  showNavCounts: true,
  locale: "en",
};

export const PREFERENCES_KEY = "admin_console_preferences";

/*
 * Storage is user-writable and survives deploys, so a value can be anything: a stale enum from an
 * older release, a hand-edited string, a whole different shape. Every field is validated rather
 * than spread, because an unrecognised theme reaches <html data-theme="..."> and matches no
 * stylesheet rule at all — which renders an unstyled, unreadable page.
 */
function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function bool(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function coerce(raw: string | null): ConsolePreferences {
  if (!raw) return DEFAULT_PREFERENCES;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return DEFAULT_PREFERENCES;
  }
  if (typeof parsed !== "object" || parsed === null) return DEFAULT_PREFERENCES;

  const stored = parsed as Partial<Record<keyof ConsolePreferences, unknown>>;
  return {
    theme: pick(stored.theme, ["dark", "light"] as const, DEFAULT_PREFERENCES.theme),
    reduceMotion: bool(stored.reduceMotion, DEFAULT_PREFERENCES.reduceMotion),
    density: pick(stored.density, ["comfortable", "compact"] as const, DEFAULT_PREFERENCES.density),
    textSize: pick(stored.textSize, ["default", "large"] as const, DEFAULT_PREFERENCES.textSize),
    showShortcuts: bool(stored.showShortcuts, DEFAULT_PREFERENCES.showShortcuts),
    showNavCounts: bool(stored.showNavCounts, DEFAULT_PREFERENCES.showNavCounts),
    locale: pick(stored.locale, ["en", "fr", "ar"] as const, DEFAULT_PREFERENCES.locale),
  };
}

export function readPreferences(): ConsolePreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    return coerce(window.localStorage.getItem(PREFERENCES_KEY));
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: ConsolePreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
  } catch {
    /* storage disabled — the session-scoped value still applies */
  }
  applyPreferences(next);
}

/** Single place that touches the document. Attributes only, never inline styles. */
export function applyPreferences(next: ConsolePreferences): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset["theme"] = next.theme;
  root.dataset["reduceMotion"] = String(next.reduceMotion);
  root.dataset["density"] = next.density;
  root.dataset["textSize"] = next.textSize;
  root.dataset["shortcuts"] = String(next.showShortcuts);
  // `color-scheme` drives form controls, scrollbars and the native focus ring.
  root.style.colorScheme = next.theme;
  // lang drives hyphenation, quotation marks and screen-reader pronunciation; dir mirrors the
  // whole layout through the CSS logical properties the shell is built on.
  root.lang = next.locale;
  root.dir = next.locale === "ar" ? "rtl" : "ltr";
}

/*
 * The blocking <head> script. Plain ES5, because it runs before the bundle, and it must mirror
 * applyPreferences exactly: whatever it fails to set is a setting that visibly reverts on reload.
 * This is what prevents a light-theme user seeing a black flash on every navigation.
 */
export const PREFERENCES_BOOT_SCRIPT = [
  "(function(){var d=document.documentElement,p=null;",
  // Read and parse in their own try: a corrupted entry must fall through to the defaults, not
  // abort the whole script and leave <html> bare.
  "try{var r=localStorage.getItem(" + JSON.stringify(PREFERENCES_KEY) + ");",
  "if(r){p=JSON.parse(r);}}catch(e){}",
  'if(!p||typeof p!=="object"){p={};}',
  'try{var t=p.theme==="light"?"light":"dark";d.dataset.theme=t;d.style.colorScheme=t;',
  'd.dataset.reduceMotion=p.reduceMotion===true?"true":"false";',
  'd.dataset.density=p.density==="compact"?"compact":"comfortable";',
  'd.dataset.textSize=p.textSize==="large"?"large":"default";',
  'd.dataset.shortcuts=p.showShortcuts===true?"true":"false";',
  // Language and direction must be painted before first render too: hydrating LTR and flipping to
  // RTL one frame later visibly throws the whole layout across the screen.
  'var l=p.locale==="fr"||p.locale==="ar"?p.locale:"en";d.lang=l;',
  'd.dir=l==="ar"?"rtl":"ltr";}catch(e){}})();',
].join("");

/* -------------------------------------------------------------------------- *
 * Store. useSyncExternalStore rather than useState: the server render has no
 * localStorage, so a lazy useState initialiser hydrates from the wrong value
 * and the toggles render out of sync with the document.
 * -------------------------------------------------------------------------- */

let cache: ConsolePreferences | null = null;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function clientSnapshot(): ConsolePreferences {
  if (cache === null) cache = readPreferences();
  return cache;
}

function serverSnapshot(): ConsolePreferences {
  return DEFAULT_PREFERENCES;
}

/** Keeps two open tabs in agreement. */
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

/** Reactive read. Returns the defaults during SSR and the stored values after hydration. */
export function usePreferences(): ConsolePreferences {
  return useSyncExternalStore(subscribe, clientSnapshot, serverSnapshot);
}

/** Merge, persist, apply to the document, and wake every subscriber. */
export function updatePreferences(patch: Partial<ConsolePreferences>): ConsolePreferences {
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
