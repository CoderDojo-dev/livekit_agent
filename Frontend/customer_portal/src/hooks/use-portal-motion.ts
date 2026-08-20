import { useReducedMotion } from "motion/react";
import { usePreferences } from "@/lib/preferences";

/**
 * The single reduced-motion answer for the portal.
 *
 * styles.css only silences CSS transitions; every JS-driven animation runs
 * through Framer Motion, and motion/react's useReducedMotion reads the OS
 * media query alone. A "Reduce motion" switch that leaves the orb and the
 * stage animating is the same class of bug as a language toggle that changes
 * nothing, so the two sources are combined here and nowhere else.
 */
export function usePortalReducedMotion(): boolean {
  const system = useReducedMotion();
  const { reduceMotion } = usePreferences();
  return Boolean(system) || reduceMotion;
}
