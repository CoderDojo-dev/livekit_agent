import { useReducedMotion } from "framer-motion";

/**
 * Motion vocabulary — the non-component half.
 *
 * Split out of components/nexus/motion.tsx so that file exports components ONLY: react-refresh
 * cannot hot-reload a module that mixes components with constants and hooks, and these are edited
 * far less often than the components that consume them.
 *
 * Values here mirror the CSS tokens in styles.css exactly, so a framer-motion transition and a
 * plain CSS one are indistinguishable in the finished UI.
 */

/** cubic-bezier(0.16, 1, 0.3, 1) — the --ease-out token from styles.css. */
export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
/** cubic-bezier(0.65, 0, 0.35, 1) — the --ease-in-out token from styles.css. */
export const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

/** Seconds. Mirrors the 120/160/200/240ms ladder the CSS transitions already use. */
export const DURATION = {
  fast: 0.12,
  base: 0.16,
  slow: 0.2,
  reveal: 0.24,
} as const;

/**
 * Reduced-motion preference, hardened.
 *
 * framer-motion's `useReducedMotion` reads `window.matchMedia`. Where that API is absent — jsdom,
 * and some embedded webviews — it does not return null; it returns its initial `false`, which is
 * indistinguishable from a genuine "full motion, please". An environment that cannot answer the
 * question would therefore silently receive full motion, including exit animations that may never
 * settle.
 *
 * So the capability check comes FIRST and overrides the report: if the preference cannot be
 * determined, assume reduced. Motion is an enhancement, and "no animation" is a strictly safer
 * failure mode than "animation that never finishes".
 */
export function usePrefersReducedMotion(): boolean {
  // Called unconditionally: a hook may not sit behind an environment check.
  const reported = useReducedMotion();

  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;

  return reported ?? false;
}

/**
 * Scrim and panel transitions for <Modal>. Kept here rather than inline so every dialog in the
 * product opens and closes identically.
 */
export function useModalMotion() {
  const reduced = usePrefersReducedMotion();

  return {
    scrim: {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
      exit: { opacity: 0 },
      transition: { duration: reduced ? 0 : DURATION.base, ease: EASE_OUT },
    },
    panel: {
      initial: reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.985 },
      animate: { opacity: 1, y: 0, scale: 1 },
      exit: reduced ? { opacity: 0 } : { opacity: 0, y: 4, scale: 0.99 },
      transition: { duration: reduced ? 0 : DURATION.slow, ease: EASE_OUT },
    },
  } as const;
}
