/**
 * lib/nav.ts — les dix destinations, chapitre 11.2 (3 + 3 + 4).
 * Source unique : le rail, la barre mobile et le titre de page derivent d'ici.
 * Aucune onzieme destination.
 *
 * Every visible string is now a TRANSLATION KEY rather than a literal. The English text still
 * lives here as `label` / `title` / `subtitle` and is what `lib/i18n.ts` returns for the `en`
 * locale, so nothing renders differently until a locale is chosen — but the rail, the mobile bar
 * and the top bar all resolve through `t()`, which is what makes the language control reach the
 * navigation instead of only the chrome around it.
 */
import type { TranslationKey } from "@/lib/i18n";

export type NavItem = {
  href: string;
  /** English text. The `en` dictionary's value for `labelKey`, kept here so this file still reads
   *  as the list of destinations rather than as a list of identifiers. */
  label: string;
  labelKey: TranslationKey;
  icon: string;
  key: string;
};

export type NavSection = {
  section: string;
  sectionKey: TranslationKey;
  items: readonly NavItem[];
};

export const NAV: readonly NavSection[] = [
  {
    section: "ASSISTANT",
    sectionKey: "nav.section.ASSISTANT",
    items: [
      {
        href: "/assistant",
        label: "Assistant",
        labelKey: "nav.assistant",
        icon: "audio-lines",
        key: "G A",
      },
      {
        href: "/activity",
        label: "Activity",
        labelKey: "nav.activity",
        icon: "history",
        key: "G V",
      },
      {
        href: "/requests",
        label: "Requests",
        labelKey: "nav.requests",
        icon: "inbox",
        key: "G R",
      },
    ],
  },
  {
    section: "ACCOUNT",
    sectionKey: "nav.section.ACCOUNT",
    items: [
      {
        href: "/services",
        label: "Services",
        labelKey: "nav.services",
        icon: "layers-2",
        key: "G S",
      },
      {
        href: "/billing",
        label: "Billing",
        labelKey: "nav.billing",
        icon: "receipt-text",
        key: "G B",
      },
      { href: "/help", label: "Help", labelKey: "nav.help", icon: "life-buoy", key: "G H" },
    ],
  },
  {
    section: "SETTINGS",
    sectionKey: "nav.section.SETTINGS",
    items: [
      {
        href: "/profile",
        label: "Profile",
        labelKey: "nav.profile",
        icon: "user-round",
        key: "G P",
      },
      {
        href: "/preferences",
        label: "Preferences",
        labelKey: "nav.preferences",
        icon: "sliders-horizontal",
        key: "G F",
      },
      {
        href: "/security",
        label: "Security",
        labelKey: "nav.security",
        icon: "shield",
        key: "G K",
      },
      { href: "/about", label: "About", labelKey: "nav.about", icon: "info", key: "G I" },
    ],
  },
] as const;

/**
 * Titre et sous-titre de la barre superieure par route, chapitre 12.2.
 *
 * Keys rather than literals, for the same reason as the labels above. A `subtitle` of `null` means
 * the route genuinely has none (only /assistant, whose scene is the subject and needs no caption);
 * every other route resolves both keys through `t()`.
 */
export const PAGE_HEAD: Record<
  string,
  { titleKey: TranslationKey; subtitleKey: TranslationKey | null }
> = {
  "/assistant": { titleKey: "page.assistant.title", subtitleKey: null },
  "/activity": { titleKey: "page.activity.title", subtitleKey: "page.activity.subtitle" },
  "/requests": { titleKey: "page.requests.title", subtitleKey: "page.requests.subtitle" },
  "/services": { titleKey: "page.services.title", subtitleKey: "page.services.subtitle" },
  "/billing": { titleKey: "page.billing.title", subtitleKey: "page.billing.subtitle" },
  "/help": { titleKey: "page.help.title", subtitleKey: "page.help.subtitle" },
  "/profile": { titleKey: "page.profile.title", subtitleKey: "page.profile.subtitle" },
  "/preferences": {
    titleKey: "page.preferences.title",
    subtitleKey: "page.preferences.subtitle",
  },
  "/security": { titleKey: "page.security.title", subtitleKey: "page.security.subtitle" },
  "/about": { titleKey: "page.about.title", subtitleKey: "page.about.subtitle" },
};
