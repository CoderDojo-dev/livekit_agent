import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { brand, copy, pageTitle } from "@/lib/copy";
import { Languages, Palette, Volume2 } from "lucide-react";
import { LOCALES, LOCALE_LABEL, LOCALE_SHORT, useTranslation } from "@/lib/i18n";
import { Card, Divider, Segmented, SectionLabel, SwitchRow } from "@/components/portal/primitives";
import { PageSection, SkeletonLine } from "@/components/portal/data";
import { SettingsNav } from "@/components/portal/settings-nav";
import { updatePreferences, usePreferences } from "@/lib/preferences";
import { usePortalSession } from "@/lib/use-portal-session";
import { qk } from "@/lib/query-keys";
import { errorMessage } from "@/lib/api/errors";
import {
  AGENT_LANGUAGES,
  DEFAULT_AGENT_LANGUAGE,
  fetchProfileDetail,
  isAgentLanguage,
  setPreferredLanguage,
  type AgentLanguage,
} from "@/lib/api/me.server";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/preferences")({
  head: () => ({
    meta: [
      { title: pageTitle("Preferences") },
      {
        name: "description",
        content:
          "Presentation settings for the portal: theme, density, text size, captions, and reduced motion.",
      },
      { property: "og:title", content: brand.name },
      {
        property: "og:description",
        content: "How the portal looks, and how the assistant shows captions.",
      },
    ],
  }),
  component: PreferencesScreen,
});

const SECTIONS = [
  { id: "appearance", label: copy.preferences.nav.appearance, icon: Palette },
  { id: "voice", label: copy.preferences.nav.voice, icon: Volume2 },
  { id: "language", label: copy.preferences.nav.language, icon: Languages },
] as const;

/**
 * INTERFACE language — what the SCREEN is written in.
 *
 * Deliberately rendered directly above the agent-language control below it, because the two are
 * the portal's single most confusable pair of settings and separating them across two screens is
 * how a customer ends up with an Arabic interface, a French assistant, and no idea which control
 * did which. Side by side, each with its own sentence saying what it does NOT change, the
 * distinction takes one read.
 *
 * This one is presentation-only: localStorage, applied to <html lang/dir>, never sent anywhere.
 */
function InterfaceLanguageRow() {
  const { locale, t } = useTranslation();

  return (
    <div>
      <div className="t-label text-ink-4">{t("preferences.interfaceLanguage")}</div>
      <p className="t-caption mt-sp-2 max-w-xl text-ink-4">
        {t("preferences.interfaceLanguageHint")}
      </p>
      <div
        role="group"
        aria-label={t("preferences.interfaceLanguage")}
        className="mt-sp-5 inline-flex overflow-hidden rounded-r-2 border border-stroke-default"
      >
        {LOCALES.map((option, index) => {
          const selected = option === locale;
          return (
            <button
              key={option}
              type="button"
              /* Each option declares its own language and direction so the browser shapes the
                 Arabic label correctly even while the page around it is still in English. */
              lang={option}
              dir={option === "ar" ? "rtl" : "ltr"}
              onClick={() => updatePreferences({ locale: option })}
              aria-pressed={selected}
              className={cn(
                "focus-ring t-label flex h-8 items-center gap-sp-3 px-sp-6 transition-colors duration-200",
                index > 0 && "border-s border-stroke-default",
                selected
                  ? "bg-n-12 text-ink-inverse"
                  : "bg-surface-2 text-ink-3 hover:bg-surface-3 hover:text-ink-1",
              )}
            >
              <span className="t-mono-s opacity-70">{LOCALE_SHORT[option]}</span>
              {LOCALE_LABEL[option]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/*
 * The saved preference is a CRM field (crm.customers.preferred_language), not a
 * browser setting, so it deliberately does NOT go through lib/preferences: that
 * store is presentation-only and never reaches a server. Adding it there would
 * be a second, silently-diverging copy of a value the agent worker reads from
 * the database at session start.
 */
function LanguageSection() {
  const session = usePortalSession();
  const queryClient = useQueryClient();
  const cid = session?.customerId ?? "unknown";
  const [pending, setPending] = useState<AgentLanguage | null>(null);

  const profile = useQuery({
    queryKey: qk.profileDetail(cid),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });

  // The column is NOT NULL with a 'fr' default, but a value the portal does not
  // recognise must read as "no preference" rather than select nothing at all.
  const stored = profile.data?.preferred_language;
  const current: AgentLanguage = isAgentLanguage(stored) ? stored : DEFAULT_AGENT_LANGUAGE;

  async function choose(language: AgentLanguage) {
    if (pending !== null) return;
    const label = copy.preferences.agentLanguageOptions[language];
    if (language === current) {
      toast.message(copy.preferences.agentLanguageUnchanged);
      return;
    }
    setPending(language);
    try {
      await setPreferredLanguage({ data: { language } });
      await queryClient.invalidateQueries({ queryKey: qk.profileDetail(cid) });
      toast.success(copy.preferences.agentLanguageSaved(label));
    } catch (caught) {
      toast.error(errorMessage(caught));
    } finally {
      setPending(null);
    }
  }

  return (
    <Card>
      <SectionLabel>{copy.preferences.language}</SectionLabel>
      <div className="mt-sp-7">
        <InterfaceLanguageRow />
      </div>
      <Divider className="my-sp-7" />
      <div>
        <div className="t-label text-ink-4">{copy.preferences.agentLanguage}</div>
        <p className="t-caption mt-sp-2 text-ink-4">{copy.preferences.agentLanguageHint}</p>
        <div className="mt-sp-5">
          {profile.isPending ? (
            <SkeletonLine className="h-8 w-56 rounded-r-2" />
          ) : (
            <div
              role="group"
              aria-label={copy.preferences.agentLanguage}
              className="inline-flex overflow-hidden rounded-r-2 border border-stroke-default"
            >
              {AGENT_LANGUAGES.map((code, i) => {
                const selected = code === current;
                const busy = pending === code;
                return (
                  <button
                    key={code}
                    type="button"
                    lang={code}
                    onClick={() => void choose(code)}
                    aria-pressed={selected}
                    aria-busy={busy}
                    disabled={pending !== null}
                    className={cn(
                      "focus-ring t-label h-8 px-sp-6 transition-colors duration-200 disabled:cursor-not-allowed",
                      i > 0 && "border-s border-stroke-default",
                      selected
                        ? "bg-n-12 text-ink-inverse"
                        : "bg-surface-2 text-ink-3 hover:bg-surface-3 hover:text-ink-1",
                      pending !== null && !busy && "opacity-60",
                    )}
                  >
                    {busy
                      ? copy.preferences.agentLanguageSaving
                      : copy.preferences.agentLanguageOptions[code]}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <Divider className="my-sp-7" />
        <p className="t-caption text-ink-4">{copy.preferences.agentLanguageNote}</p>
      </div>
    </Card>
  );
}

function PreferencesScreen() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("appearance");
  // Read through the store, not useState: the server render has no
  // localStorage, so a lazy initialiser hydrates the controls out of sync with
  // the document the head script already styled.
  const prefs = usePreferences();
  const update = updatePreferences;

  return (
    <div className="grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]">
      <SettingsNav
        sections={SECTIONS}
        value={section}
        onChange={setSection}
        label={copy.preferences.navLabel}
      />

      <div className="space-y-sp-8">
        {section === "appearance" && (
          <PageSection>
            <Card>
              <SectionLabel>{copy.preferences.appearance}</SectionLabel>
              <div className="mt-sp-7 space-y-sp-7">
                <div>
                  <div className="t-label text-ink-4">{copy.preferences.theme}</div>
                  <div className="mt-sp-4">
                    <Segmented
                      label={copy.preferences.theme}
                      options={copy.preferences.themes}
                      value={prefs.theme === "light" ? "Light" : "Dark"}
                      onChange={(v) => update({ theme: v === "Light" ? "light" : "dark" })}
                    />
                  </div>
                </div>
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
          </PageSection>
        )}

        {section === "language" && (
          <PageSection>
            <LanguageSection />
          </PageSection>
        )}

        {section === "voice" && (
          <PageSection>
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
          </PageSection>
        )}
      </div>
    </div>
  );
}
