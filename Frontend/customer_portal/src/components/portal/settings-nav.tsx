import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * components/portal/settings-nav.tsx — the section switcher for Profile,
 * Preferences and Security.
 *
 * All three screens had written this list by hand, and the three copies had
 * already drifted: Profile used `t-label` in a horizontal strip that never
 * became a column on desktop, while Preferences and Security used `t-ui` in a
 * sticky column. One component now, so the three settings screens are one
 * screen with three subjects.
 *
 * Icons are new. On a page whose whole content is words, a four-item list of
 * words is the hardest thing on it to scan; a glyph per section makes the
 * switcher readable at a glance and matches the rail two columns to the left.
 *
 * Layout: a scrollable horizontal strip below lg, a sticky column above it.
 * The strip's overflow is deliberate — three or four labels plus glyphs do not
 * fit a 375px screen, and wrapping them onto two lines pushes the card the
 * customer came for below the fold.
 */
export function SettingsNav<T extends string>({
  sections,
  value,
  onChange,
  label,
}: {
  sections: readonly { id: T; label: string; icon: LucideIcon }[];
  value: T;
  onChange: (next: T) => void;
  /** Names the group for assistive technology — "Profile sections". */
  label: string;
}) {
  return (
    <nav aria-label={label} className="lg:sticky lg:top-24 lg:self-start">
      <ul className="-mx-sp-2 flex gap-sp-2 overflow-x-auto px-sp-2 pb-sp-2 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0 lg:pb-0">
        {sections.map((section) => {
          const active = section.id === value;
          const Icon = section.icon;
          return (
            <li key={section.id} className="shrink-0 lg:shrink">
              <button
                type="button"
                onClick={() => onChange(section.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "focus-ring group relative flex h-9 w-full items-center gap-sp-5 rounded-r-2 px-sp-5 text-left transition-colors duration-200",
                  active
                    ? "bg-surface-3 text-ink-1"
                    : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                )}
              >
                {/* The same 2px leading stroke the rail uses for the active
                    destination. It fades rather than appearing, so switching
                    sections does not flicker a bar in and out. */}
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute start-0 top-1/2 hidden h-4 w-0.5 -translate-y-1/2 rounded-r-1 bg-n-12 transition-opacity duration-200 lg:block",
                    active ? "opacity-100" : "opacity-0",
                  )}
                />
                <Icon
                  size={15}
                  strokeWidth={1.5}
                  aria-hidden="true"
                  className={cn(
                    "shrink-0 transition-colors duration-200",
                    active ? "text-ink-2" : "text-ink-5 group-hover:text-ink-3",
                  )}
                />
                <span className="t-ui truncate">{section.label}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
