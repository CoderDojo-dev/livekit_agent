import { Moon, Sun } from "lucide-react";
import { updatePreferences, usePreferences } from "@/lib/preferences";
import { IconButton } from "@/components/portal/primitives";
import { useTranslation } from "@/lib/i18n";

/**
 * components/shell/theme-toggle.tsx — the theme, one click from anywhere.
 *
 * The Preferences screen stays the canonical control; this is the same store
 * (lib/preferences), not a second copy of the setting, so the two never
 * disagree and the head script still paints the right theme on reload.
 *
 * The icon shows the destination, not the current state: on a dark page the
 * sun means "go light". A toggle that shows what you already have gives the
 * user nothing to aim at.
 */
export function ThemeToggle() {
  const { theme } = usePreferences();
  const { t } = useTranslation();
  const next = theme === "dark" ? "light" : "dark";
  const Icon = next === "light" ? Sun : Moon;

  return (
    <IconButton
      label={next === "light" ? t("shell.theme.light") : t("shell.theme.dark")}
      aria-pressed={theme === "light"}
      onClick={() => updatePreferences({ theme: next })}
    >
      <Icon size={16} strokeWidth={1.5} />
    </IconButton>
  );
}
