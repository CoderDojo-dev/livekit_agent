/**
 * lib/nexus/i18n.ts — interface language for the console.
 *
 * SCOPE, stated honestly at the top because it matters more than the mechanism.
 *
 * This translates the SHELL: navigation, page titles and subtitles, and the vocabulary that
 * repeats on every screen (search, save, cancel, pagination, empty and error states). Page body
 * copy — the governance prose on /policies, the provenance notes, the KPI context lines — remains
 * English for now. Those strings are precise, legally-flavoured and frequently argued over; a
 * rough translation of "thresholds are enforced from POLICY_* environment variables" would be
 * worse than leaving it in the language it was written in.
 *
 * The mechanism below carries them the moment a translation exists: `t()` falls back to English
 * per key, so a partially filled dictionary renders a partially translated page rather than a
 * page full of missing-key markers.
 *
 * Arabic sets `dir="rtl"` on <html>. Layout uses CSS logical properties (start/end rather than
 * left/right) so the sidebar, paddings and alignment mirror without a second stylesheet.
 */

import { usePreferences } from "@/lib/nexus/preferences";

export const LOCALES = ["en", "fr", "ar"] as const;
export type Locale = (typeof LOCALES)[number];

export const LOCALE_LABEL: Record<Locale, string> = {
  en: "English",
  fr: "Français",
  ar: "العربية",
};

/** Short form for the topbar control. */
export const LOCALE_SHORT: Record<Locale, string> = {
  en: "EN",
  fr: "FR",
  ar: "ع",
};

export const RTL_LOCALES: readonly Locale[] = ["ar"];

export function isRtl(locale: Locale): boolean {
  return RTL_LOCALES.includes(locale);
}

/**
 * The English dictionary is the SOURCE OF TRUTH for the key set: its type defines what every
 * other locale may provide, so a typo in a translation is a compile error rather than a silent
 * fallback.
 */
const en = {
  /* ---- navigation sections ---- */
  "nav.section.PLATFORM": "Platform",
  "nav.section.KNOWLEDGE": "Knowledge",
  "nav.section.OPERATIONS": "Operations",
  "nav.section.INSIGHTS": "Insights",

  /* ---- navigation items ---- */
  "nav.overview": "Overview",
  "nav.customers": "Customers",
  "nav.escalations": "Escalations",
  "nav.tickets": "Tickets",
  "nav.knowledge": "Knowledge Base",
  "nav.policies": "Policies",
  "nav.reference": "Reference",
  "nav.calls": "Calls & Transcripts",
  "nav.advisors": "Advisors",
  "nav.availability": "Availability",
  "nav.callbacks": "Callbacks",
  "nav.notifications": "Notifications",
  "nav.decisions": "Decisions",
  "nav.analytics": "Analytics",
  "nav.agents": "Agents",
  "nav.audit": "Audit",
  "nav.settings": "Settings",

  /* ---- shell ---- */
  "shell.signOut": "Sign out",
  "shell.openNavigation": "Open navigation",
  "shell.theme.light": "Switch to light theme",
  "shell.theme.dark": "Switch to dark theme",
  "shell.language": "Language",
  "shell.primaryNavigation": "Primary",

  /* ---- repeated vocabulary ---- */
  "common.search": "Search",
  "common.save": "Save changes",
  "common.cancel": "Cancel",
  "common.retry": "Try again",
  "common.loading": "Loading",
  "common.all": "All",
  "common.none": "None",

  /* ---- pagination ---- */
  "pager.previous": "Previous page",
  "pager.next": "Next page",
  "pager.page": "Page",
  "pager.showing": "Showing",
  "pager.of": "of",
  "pager.noRows": "No rows",

  /* ---- states ---- */
  "state.empty": "Nothing to show",
  "state.error": "Could not load",
  "state.forbidden": "Access denied",
  "state.expired": "Session expired",
} as const;

export type TranslationKey = keyof typeof en;
type Dictionary = Partial<Record<TranslationKey, string>>;

const fr: Dictionary = {
  "nav.section.PLATFORM": "Plateforme",
  "nav.section.KNOWLEDGE": "Connaissances",
  "nav.section.OPERATIONS": "Opérations",
  "nav.section.INSIGHTS": "Analyses",

  "nav.overview": "Vue d'ensemble",
  "nav.customers": "Clients",
  "nav.escalations": "Escalades",
  "nav.tickets": "Tickets",
  "nav.knowledge": "Base de connaissances",
  "nav.policies": "Politiques",
  "nav.reference": "Référentiel",
  "nav.calls": "Appels et transcriptions",
  "nav.advisors": "Conseillers",
  "nav.availability": "Disponibilité",
  "nav.callbacks": "Rappels",
  "nav.notifications": "Notifications",
  "nav.decisions": "Décisions",
  "nav.analytics": "Analytique",
  "nav.agents": "Agents",
  "nav.audit": "Audit",
  "nav.settings": "Paramètres",

  "shell.signOut": "Se déconnecter",
  "shell.openNavigation": "Ouvrir la navigation",
  "shell.theme.light": "Passer au thème clair",
  "shell.theme.dark": "Passer au thème sombre",
  "shell.language": "Langue",
  "shell.primaryNavigation": "Principale",

  "common.search": "Rechercher",
  "common.save": "Enregistrer",
  "common.cancel": "Annuler",
  "common.retry": "Réessayer",
  "common.loading": "Chargement",
  "common.all": "Tous",
  "common.none": "Aucun",

  "pager.previous": "Page précédente",
  "pager.next": "Page suivante",
  "pager.page": "Page",
  "pager.showing": "Affichage",
  "pager.of": "sur",
  "pager.noRows": "Aucune ligne",

  "state.empty": "Rien à afficher",
  "state.error": "Chargement impossible",
  "state.forbidden": "Accès refusé",
  "state.expired": "Session expirée",
};

const ar: Dictionary = {
  "nav.section.PLATFORM": "المنصة",
  "nav.section.KNOWLEDGE": "المعرفة",
  "nav.section.OPERATIONS": "العمليات",
  "nav.section.INSIGHTS": "التحليلات",

  "nav.overview": "نظرة عامة",
  "nav.customers": "العملاء",
  "nav.escalations": "التصعيدات",
  "nav.tickets": "التذاكر",
  "nav.knowledge": "قاعدة المعرفة",
  "nav.policies": "السياسات",
  "nav.reference": "المراجع",
  "nav.calls": "المكالمات والنصوص",
  "nav.advisors": "المستشارون",
  "nav.availability": "التوفر",
  "nav.callbacks": "معاودة الاتصال",
  "nav.notifications": "الإشعارات",
  "nav.decisions": "القرارات",
  "nav.analytics": "التحليلات",
  "nav.agents": "الوكلاء",
  "nav.audit": "التدقيق",
  "nav.settings": "الإعدادات",

  "shell.signOut": "تسجيل الخروج",
  "shell.openNavigation": "فتح التنقل",
  "shell.theme.light": "التبديل إلى الوضع الفاتح",
  "shell.theme.dark": "التبديل إلى الوضع الداكن",
  "shell.language": "اللغة",
  "shell.primaryNavigation": "الرئيسية",

  "common.search": "بحث",
  "common.save": "حفظ التغييرات",
  "common.cancel": "إلغاء",
  "common.retry": "إعادة المحاولة",
  "common.loading": "جارٍ التحميل",
  "common.all": "الكل",
  "common.none": "لا شيء",

  "pager.previous": "الصفحة السابقة",
  "pager.next": "الصفحة التالية",
  "pager.page": "صفحة",
  "pager.showing": "عرض",
  "pager.of": "من",
  "pager.noRows": "لا توجد صفوف",

  "state.empty": "لا شيء لعرضه",
  "state.error": "تعذر التحميل",
  "state.forbidden": "تم رفض الوصول",
  "state.expired": "انتهت الجلسة",
};

const DICTIONARIES: Record<Locale, Dictionary> = { en, fr, ar };

/**
 * Translate one key.
 *
 * Falls back to English PER KEY rather than per locale, so an incomplete translation degrades
 * one string at a time instead of dropping the whole page back to English — and never renders a
 * raw key at the user.
 */
export function translate(locale: Locale, key: TranslationKey): string {
  return DICTIONARIES[locale]?.[key] ?? en[key];
}

/** Reactive translator bound to the stored preference. */
export function useTranslation() {
  const { locale } = usePreferences();

  return {
    locale,
    rtl: isRtl(locale),
    t: (key: TranslationKey) => translate(locale, key),
  };
}
