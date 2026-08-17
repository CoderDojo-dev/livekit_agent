/**
 * lib/preferences.ts — presentation settings only.
 *
 * Nothing here is sent to a server, because no preferences table exists in
 * version_92 and inventing one would change backend behaviour. Every value is
 * a pure rendering choice applied as a data-attribute on <html>.
 */
export type Density = "comfortable" | "compact";
export type TextSize = "default" | "large";

export type PortalPreferences = {
  reduceMotion: boolean;
  density: Density;
  textSize: TextSize;
  captions: boolean;
};

export const DEFAULT_PREFERENCES: PortalPreferences = {
  reduceMotion: false,
  density: "comfortable",
  textSize: "default",
  captions: true,
};

const KEY = "nexus_portal_preferences";

export function readPreferences(): PortalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<PortalPreferences>) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: PortalPreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage disabled — the session-scoped value still applies */
  }
  applyPreferences(next);
}

/** Single place that touches the document. Attributes only, never inline styles. */
export function applyPreferences(next: PortalPreferences): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset["reduceMotion"] = String(next.reduceMotion);
  root.dataset["density"] = next.density;
  root.dataset["textSize"] = next.textSize;
}
