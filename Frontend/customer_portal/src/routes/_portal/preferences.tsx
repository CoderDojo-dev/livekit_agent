import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { copy } from "@/lib/copy";
import { Card, Divider, Segmented, SectionLabel, SwitchRow } from "@/components/portal/primitives";
import {
  readPreferences,
  writePreferences,
  type PortalPreferences,
} from "@/lib/preferences";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/preferences")({
  head: () => ({
    meta: [
      { title: "Preferences — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Presentation settings for the portal: density, text size, captions, and reduced motion.",
      },
      { property: "og:title", content: "Preferences — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "How the portal looks, and how the assistant shows captions.",
      },
    ],
  }),
  component: PreferencesScreen,
});

const SECTIONS = [
  { id: "appearance", label: copy.preferences.nav.appearance },
  { id: "voice", label: copy.preferences.nav.voice },
] as const;

function PreferencesScreen() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("appearance");
  const [prefs, setPrefs] = useState<PortalPreferences>(() => readPreferences());

  function update(next: Partial<PortalPreferences>) {
    const merged = { ...prefs, ...next };
    setPrefs(merged);
    writePreferences(merged);
  }

  return (
    <div className="grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav className="lg:sticky lg:top-24 lg:self-start">
        <ul className="space-y-sp-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setSection(s.id)}
                className={cn(
                  "focus-ring t-ui flex h-9 w-full items-center rounded-r-2 px-sp-5 text-left transition-colors duration-200",
                  section === s.id
                    ? "bg-surface-3 text-ink-1"
                    : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                )}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-sp-8">
        {section === "appearance" && (
          <Card>
            <SectionLabel>{copy.preferences.appearance}</SectionLabel>
            <div className="mt-sp-7 space-y-sp-7">
              <div>
                <div className="t-label text-ink-4">{copy.preferences.density}</div>
                <div className="mt-sp-4">
                  <Segmented
                    label={copy.preferences.density}
                    options={copy.preferences.densities}
                    value={prefs.density === "compact" ? "Compact" : "Comfortable"}
                    onChange={(v) =>
                      update({ density: v === "Compact" ? "compact" : "comfortable" })
                    }
                  />
                </div>
              </div>
              <div>
                <div className="t-label text-ink-4">{copy.preferences.textSize}</div>
                <div className="mt-sp-4">
                  <Segmented
                    label={copy.preferences.textSize}
                    options={copy.preferences.textSizes}
                    value={prefs.textSize === "large" ? "Large" : "Default"}
                    onChange={(v) => update({ textSize: v === "Large" ? "large" : "default" })}
                  />
                </div>
              </div>
              <Divider />
              <SwitchRow
                {...copy.preferences.switches.reduceMotion}
                checked={prefs.reduceMotion}
                onChange={(v) => update({ reduceMotion: v })}
              />
              <p className="t-caption text-ink-4">{copy.preferences.reduceMotionNote}</p>
            </div>
          </Card>
        )}

        {section === "voice" && (
          <Card>
            <SectionLabel>{copy.preferences.voice}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <SwitchRow
                {...copy.preferences.switches.captions}
                checked={prefs.captions}
                onChange={(v) => update({ captions: v })}
              />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
