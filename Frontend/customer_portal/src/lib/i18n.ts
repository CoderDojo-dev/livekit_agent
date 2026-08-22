/**
 * lib/i18n.ts — interface language for the customer portal.
 *
 * Ported from the admin console's lib/nexus/i18n.ts rather than reinvented, so the two front ends
 * behave identically: same locale set, same per-key English fallback, same RTL rule.
 *
 * SCOPE, stated at the top because it matters more than the mechanism.
 * ---------------------------------------------------------------------------------------------
 * This translates the SHELL: the ten navigation destinations, the page title and subtitle in the
 * top bar, the account and notification menus, and the vocabulary that repeats on every screen.
 * Page BODY copy — the assistant's nine state sentences, the help answers, the billing and
 * services prose in lib/copy.ts — stays in English for now. That deck is a thousand lines of
 * carefully argued product writing, and a rough translation of it would be worse than leaving it
 * in the language it was written in.
 *
 * `t()` falls back to English PER KEY, so the moment a translation is added it renders, and a
 * partially filled dictionary produces a partially translated page rather than a page full of
 * missing-key markers. Nothing here can ever render a raw key at a customer.
 *
 * TWO LANGUAGES THAT ARE NOT THE SAME THING.
 * ---------------------------------------------------------------------------------------------
 * The portal already had a language setting: `preferences.agentLanguage`, which writes
 * crm.customers.preferred_language and decides what language a VOICE CONVERSATION opens in. It is
 * an account fact the agent-worker reads at session start.
 *
 * This is a different setting with a different lifetime. It is presentation only, it lives in
 * localStorage beside the theme, it never reaches a server, and it changes what the SCREEN says —
 * not what the assistant speaks. Both are exposed under Preferences, side by side and separately
 * labelled, because a customer who confuses them ends up with an Arabic interface and a French
 * assistant and no idea which control did which.
 *
 * ARABIC SETS dir="rtl" on <html>. The shell is written with CSS logical properties
 * (start/end rather than left/right), so the rail, the paddings and the sheets mirror without a
 * second stylesheet.
 */

import { usePreferences } from "@/lib/preferences";

export const LOCALES = ["en", "fr", "ar"] as const;
export type Locale = (typeof LOCALES)[number];

/** Each language written in ITSELF — the one label a speaker of it always recognises. */
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
 * fallback to English that nobody notices for a release.
 */
const en = {
  /* ---- navigation sections (lib/nav.ts) ---- */
  "nav.section.ASSISTANT": "Assistant",
  "nav.section.ACCOUNT": "Account",
  "nav.section.SETTINGS": "Settings",

  /* ---- the ten destinations ---- */
  "nav.assistant": "Assistant",
  "nav.activity": "Activity",
  "nav.requests": "Requests",
  "nav.services": "Services",
  "nav.billing": "Billing",
  "nav.help": "Help",
  "nav.profile": "Profile",
  "nav.preferences": "Preferences",
  "nav.security": "Security",
  "nav.about": "About",

  /* ---- page heads (the top bar's title + subtitle) ---- */
  "page.assistant.title": "Assistant",
  "page.assistant.subtitle": "",
  "page.activity.title": "Activity",
  "page.activity.subtitle": "Everything you and the assistant have done together.",
  "page.requests.title": "Requests",
  "page.requests.subtitle": "Things we are working on for you.",
  "page.services.title": "Services",
  "page.services.subtitle": "What you have with us today.",
  "page.billing.title": "Billing",
  "page.billing.subtitle": "Invoices, payment methods, and what is coming next.",
  "page.help.title": "Help",
  "page.help.subtitle": "Answers, guides, and a way to reach a person.",
  "page.profile.title": "Profile",
  "page.profile.subtitle": "Who you are and how we reach you.",
  "page.preferences.title": "Preferences",
  "page.preferences.subtitle": "How the assistant behaves and how the portal looks.",
  "page.security.title": "Security",
  "page.security.subtitle": "Sign-in, devices, and your data.",
  "page.about.title": "About",
  "page.about.subtitle": "What the assistant is, and what it is not.",

  /* ---- shell chrome ---- */
  "shell.account": "Account",
  "shell.signOut": "Sign out",
  "shell.notifications": "Notifications",
  "shell.notificationsEmpty": "Nothing new.",
  "shell.secure": "SECURE",
  "shell.language": "Language",
  "shell.collapseRail": "Collapse navigation",
  "shell.expandRail": "Expand navigation",
  "shell.theme.light": "Switch to light theme",
  "shell.theme.dark": "Switch to dark theme",
  "shell.menu.profile": "Your profile",
  "shell.menu.security": "Security",
  "shell.notifications.heading": "RECENT MESSAGES",
  "shell.notifications.seeAll": "See every message",

  /* ---- repeated vocabulary ---- */
  "common.close": "Close",
  "common.retry": "Try again",
  "common.loading": "Loading",
  "common.search": "Search",
  "common.previous": "Previous page",
  "common.next": "Next page",
  "common.couldNotLoad": "We could not load this",

  /* ---- the interface-language setting itself ---- */
  "preferences.interfaceLanguage": "Interface language",
  "preferences.interfaceLanguageHint":
    "Changes the navigation, page titles and menus in this browser. It does not change the language the assistant speaks.",
} as const;

export type TranslationKey = keyof typeof en;
type Dictionary = Partial<Record<TranslationKey, string>>;

const fr: Dictionary = {
  "nav.section.ASSISTANT": "Assistant",
  "nav.section.ACCOUNT": "Compte",
  "nav.section.SETTINGS": "Réglages",

  "nav.assistant": "Assistant",
  "nav.activity": "Activité",
  "nav.requests": "Demandes",
  "nav.services": "Services",
  "nav.billing": "Facturation",
  "nav.help": "Aide",
  "nav.profile": "Profil",
  "nav.preferences": "Préférences",
  "nav.security": "Sécurité",
  "nav.about": "À propos",

  "page.assistant.title": "Assistant",
  "page.activity.title": "Activité",
  "page.activity.subtitle": "Tout ce que vous avez fait avec l'assistant.",
  "page.requests.title": "Demandes",
  "page.requests.subtitle": "Ce sur quoi nous travaillons pour vous.",
  "page.services.title": "Services",
  "page.services.subtitle": "Ce dont vous disposez aujourd'hui.",
  "page.billing.title": "Facturation",
  "page.billing.subtitle": "Factures, moyens de paiement et prochaines échéances.",
  "page.help.title": "Aide",
  "page.help.subtitle": "Des réponses, des guides, et un moyen de joindre une personne.",
  "page.profile.title": "Profil",
  "page.profile.subtitle": "Qui vous êtes et comment vous joindre.",
  "page.preferences.title": "Préférences",
  "page.preferences.subtitle": "Le comportement de l'assistant et l'apparence du portail.",
  "page.security.title": "Sécurité",
  "page.security.subtitle": "Connexion, appareils et vos données.",
  "page.about.title": "À propos",
  "page.about.subtitle": "Ce qu'est l'assistant, et ce qu'il n'est pas.",

  "shell.account": "Compte",
  "shell.signOut": "Se déconnecter",
  "shell.notifications": "Notifications",
  "shell.notificationsEmpty": "Rien de nouveau.",
  "shell.secure": "SÉCURISÉ",
  "shell.language": "Langue",
  "shell.collapseRail": "Réduire la navigation",
  "shell.expandRail": "Déployer la navigation",
  "shell.theme.light": "Passer au thème clair",
  "shell.theme.dark": "Passer au thème sombre",
  "shell.menu.profile": "Votre profil",
  "shell.menu.security": "Sécurité",
  "shell.notifications.heading": "MESSAGES RÉCENTS",
  "shell.notifications.seeAll": "Voir tous les messages",

  "common.close": "Fermer",
  "common.retry": "Réessayer",
  "common.loading": "Chargement",
  "common.search": "Rechercher",
  "common.previous": "Page précédente",
  "common.next": "Page suivante",
  "common.couldNotLoad": "Nous n'avons pas pu charger ceci",

  "preferences.interfaceLanguage": "Langue de l'interface",
  "preferences.interfaceLanguageHint":
    "Change la navigation, les titres de page et les menus dans ce navigateur. Ne change pas la langue parlée par l'assistant.",
};

const ar: Dictionary = {
  "nav.section.ASSISTANT": "المساعد",
  "nav.section.ACCOUNT": "الحساب",
  "nav.section.SETTINGS": "الإعدادات",

  "nav.assistant": "المساعد",
  "nav.activity": "النشاط",
  "nav.requests": "الطلبات",
  "nav.services": "الخدمات",
  "nav.billing": "الفوترة",
  "nav.help": "المساعدة",
  "nav.profile": "الملف الشخصي",
  "nav.preferences": "التفضيلات",
  "nav.security": "الأمان",
  "nav.about": "حول",

  "page.assistant.title": "المساعد",
  "page.activity.title": "النشاط",
  "page.activity.subtitle": "كل ما قمت به أنت والمساعد معًا.",
  "page.requests.title": "الطلبات",
  "page.requests.subtitle": "ما نعمل عليه من أجلك.",
  "page.services.title": "الخدمات",
  "page.services.subtitle": "ما لديك معنا اليوم.",
  "page.billing.title": "الفوترة",
  "page.billing.subtitle": "الفواتير ووسائل الدفع وما هو قادم.",
  "page.help.title": "المساعدة",
  "page.help.subtitle": "إجابات وأدلة وطريقة للتواصل مع شخص.",
  "page.profile.title": "الملف الشخصي",
  "page.profile.subtitle": "من أنت وكيف نتواصل معك.",
  "page.preferences.title": "التفضيلات",
  "page.preferences.subtitle": "كيف يتصرف المساعد وكيف تبدو البوابة.",
  "page.security.title": "الأمان",
  "page.security.subtitle": "تسجيل الدخول والأجهزة وبياناتك.",
  "page.about.title": "حول",
  "page.about.subtitle": "ما هو المساعد، وما ليس هو.",

  "shell.account": "الحساب",
  "shell.signOut": "تسجيل الخروج",
  "shell.notifications": "الإشعارات",
  "shell.notificationsEmpty": "لا جديد.",
  "shell.secure": "آمن",
  "shell.language": "اللغة",
  "shell.collapseRail": "طي شريط التنقل",
  "shell.expandRail": "توسيع شريط التنقل",
  "shell.theme.light": "التبديل إلى الوضع الفاتح",
  "shell.theme.dark": "التبديل إلى الوضع الداكن",
  "shell.menu.profile": "ملفك الشخصي",
  "shell.menu.security": "الأمان",
  "shell.notifications.heading": "الرسائل الأخيرة",
  "shell.notifications.seeAll": "عرض كل الرسائل",

  "common.close": "إغلاق",
  "common.retry": "إعادة المحاولة",
  "common.loading": "جارٍ التحميل",
  "common.search": "بحث",
  "common.previous": "الصفحة السابقة",
  "common.next": "الصفحة التالية",
  "common.couldNotLoad": "تعذر تحميل هذا",

  "preferences.interfaceLanguage": "لغة الواجهة",
  "preferences.interfaceLanguageHint":
    "تغيّر التنقل وعناوين الصفحات والقوائم في هذا المتصفح. لا تغيّر اللغة التي يتحدث بها المساعد.",
};

const DICTIONARIES: Record<Locale, Dictionary> = { en, fr, ar };

/**
 * Translate one key.
 *
 * Falls back to English PER KEY rather than per locale, so an incomplete translation degrades one
 * string at a time instead of dropping the whole page back to English.
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
