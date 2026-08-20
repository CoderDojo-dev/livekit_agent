import { Moon, Sun } from "lucide-react";
import { updatePreferences, usePreferences } from "@/lib/nexus/preferences";
import { IconButton } from "@/components/nexus/primitives";

/**
 * The theme, one click from anywhere.
 *
 * Settings stays the canonical control; this is the SAME store (lib/nexus/preferences), not a
 * second copy of the setting, so the two can never disagree and the pre-paint head script still
 * paints the right theme on reload.
 *
 * The icon shows the DESTINATION, not the current state: on a dark page the sun means "go light".
 * A toggle that pictures what you already have gives the user nothing to aim at.
 *
 * Dark remains the product's native mode — this switches away from it, it does not replace it.
 */
export function ThemeToggle() {
  const { theme } = usePreferences();
  const next = theme === "dark" ? "light" : "dark";
  const Icon = next === "light" ? Sun : Moon;

  return (
    <IconButton
      label={next === "light" ? "Switch to light theme" : "Switch to dark theme"}
      icon={Icon}
      aria-pressed={theme === "light"}
      onClick={() => updatePreferences({ theme: next })}
    />
  );
}
