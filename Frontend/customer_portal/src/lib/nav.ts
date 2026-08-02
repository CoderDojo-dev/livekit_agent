/**
 * lib/nav.ts — les onze destinations, chapitre 11.2.
 * Aucune douzieme destination.
 */
export type NavItem = {
  href: string;
  label: string;
  icon: string;
  key: string;
};

export type NavSection = {
  section: string;
  items: readonly NavItem[];
};

export const NAV: readonly NavSection[] = [
  {
    section: "ASSISTANT",
    items: [
      { href: "/assistant", label: "Assistant", icon: "audio-lines", key: "G A" },
      { href: "/activity", label: "Activity", icon: "history", key: "G V" },
      { href: "/requests", label: "Requests", icon: "inbox", key: "G R" },
    ],
  },
  {
    section: "ACCOUNT",
    items: [
      { href: "/services", label: "Services", icon: "layers-2", key: "G S" },
      { href: "/billing", label: "Billing", icon: "receipt-text", key: "G B" },
      { href: "/help", label: "Help", icon: "life-buoy", key: "G H" },
    ],
  },
  {
    section: "SETTINGS",
    items: [
      { href: "/profile", label: "Profile", icon: "user-round", key: "G P" },
      { href: "/preferences", label: "Preferences", icon: "sliders-horizontal", key: "G F" },
      { href: "/security", label: "Security", icon: "shield", key: "G K" },
      { href: "/about", label: "About", icon: "info", key: "G I" },
    ],
  },
] as const;

/** Titre et sous-titre de la barre superieure par route, chapitre 12.2. */
export const PAGE_HEAD: Record<string, { title: string; subtitle: string | null }> = {
  "/assistant": { title: "Assistant", subtitle: null },
  "/activity": {
    title: "Activity",
    subtitle: "Everything you and the assistant have done together.",
  },
  "/requests": { title: "Requests", subtitle: "Things we are working on for you." },
  "/services": { title: "Services", subtitle: "What you have with us today." },
  "/billing": {
    title: "Billing",
    subtitle: "Invoices, payment methods, and what is coming next.",
  },
  "/help": { title: "Help", subtitle: "Answers, guides, and a way to reach a person." },
  "/profile": { title: "Profile", subtitle: "Who you are and how we reach you." },
  "/preferences": {
    title: "Preferences",
    subtitle: "How the assistant behaves and how the portal looks.",
  },
  "/security": { title: "Security", subtitle: "Sign-in, devices, and your data." },
  "/about": { title: "About", subtitle: "What the assistant is, and what it is not." },
};
