/**
 * Motion language — single source of truth for all call-UI animations.
 *
 * These values mirror the CSS custom properties defined in `index.css`
 * (`--ease-smooth`, `--dur-micro`, `--dur-base`, `--dur-macro`). Keep the two
 * in sync: the CSS tokens drive stage/layout transitions, these drive the
 * `motion` (framer) animations. One vocabulary, one feel.
 *
 * Durations are in seconds (what `motion` expects); the CSS tokens are the
 * same values in milliseconds.
 */

/** Canonical enter/settle curve (ease-out-expo). Matches `--ease-smooth`. */
export const EASE_SMOOTH = [0.16, 1, 0.3, 1] as const;

/** Gentle accelerate-away curve for elements leaving. Matches `--ease-exit`. */
export const EASE_EXIT = [0.55, 0, 0.85, 0] as const;

/** Duration scale (seconds). Mirrors `--dur-micro` / `--dur-base` / `--dur-macro`. */
export const DURATION = {
  micro: 0.32, // small opacity / fades
  base: 0.5, // standard element moves, transcript turns, toolbar swap
  macro: 0.68, // large stage layout shifts
} as const;

/** Ready-made transitions so call components stay consistent. */
export const TRANSITION_MICRO = { duration: DURATION.micro, ease: EASE_SMOOTH } as const;
export const TRANSITION_BASE = { duration: DURATION.base, ease: EASE_SMOOTH } as const;
export const TRANSITION_MACRO = { duration: DURATION.macro, ease: EASE_SMOOTH } as const;
