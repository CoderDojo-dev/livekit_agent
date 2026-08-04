// Chapter 11.7 — the twelve destinations. Source of truth for navigation.
import {
  LayoutDashboard,
  Users,
  LifeBuoy,
  Ticket,
  BookOpen,
  ScrollText,
  GitBranch,
  Phone,
  Headset,
  PhoneOutgoing,
  CalendarClock,
  BarChart3,
  Scale,
  Settings,
  Bot,
  type LucideIcon,
} from "lucide-react";

export type NavSection = "PLATFORM" | "KNOWLEDGE" | "OPERATIONS" | "INSIGHTS";

export type NavItem = {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  section: NavSection;
  badge?: number;
  badgeVariant?: "count" | "live";
  shortcut: string;
};

export const NAV: readonly NavItem[] = [
  {
    id: "overview",
    label: "Overview",
    href: "/overview",
    icon: LayoutDashboard,
    section: "PLATFORM",
    shortcut: "G O",
  },
  {
    id: "customers",
    label: "Customers",
    href: "/customers",
    icon: Users,
    section: "PLATFORM",
    shortcut: "G C",
  },
  {
    id: "escalations",
    label: "Escalations",
    href: "/escalations",
    icon: LifeBuoy,
    section: "PLATFORM",
    shortcut: "G E",
  },
  {
    id: "tickets",
    label: "Tickets",
    href: "/tickets",
    icon: Ticket,
    section: "PLATFORM",
    shortcut: "G T",
    badge: 42,
    badgeVariant: "count",
  },
  {
    id: "knowledge",
    label: "Knowledge Base",
    href: "/knowledge",
    icon: BookOpen,
    section: "KNOWLEDGE",
    shortcut: "G K",
  },
  {
    id: "policies",
    label: "Policies",
    href: "/policies",
    icon: ScrollText,
    section: "KNOWLEDGE",
    shortcut: "G P",
  },
  {
    id: "reference",
    label: "Reference",
    href: "/reference",
    icon: GitBranch,
    section: "KNOWLEDGE",
    shortcut: "G R",
  },
  {
    id: "calls",
    label: "Calls & Transcripts",
    href: "/calls",
    icon: Phone,
    section: "OPERATIONS",
    shortcut: "G L",
  },
  {
    id: "advisors",
    label: "Advisors",
    href: "/advisors",
    icon: Headset,
    section: "OPERATIONS",
    shortcut: "G A",
  },
  {
    id: "availability",
    label: "Availability",
    href: "/availability",
    icon: CalendarClock,
    section: "OPERATIONS",
    shortcut: "G D",
  },
  {
    id: "callbacks",
    label: "Callbacks",
    href: "/callbacks",
    icon: PhoneOutgoing,
    section: "OPERATIONS",
    shortcut: "G B",
    badge: 7,
    badgeVariant: "count",
  },
  {
    id: "decisions",
    label: "Decisions",
    href: "/decisions",
    icon: Scale,
    section: "INSIGHTS",
    shortcut: "G J",
  },
  {
    id: "analytics",
    label: "Analytics",
    href: "/analytics",
    icon: BarChart3,
    section: "INSIGHTS",
    shortcut: "G N",
  },
  {
    id: "agents",
    label: "Agents",
    href: "/agents",
    icon: Bot,
    section: "INSIGHTS",
    shortcut: "G G",
  },
  {
    id: "settings",
    label: "Settings",
    href: "/settings",
    icon: Settings,
    section: "INSIGHTS",
    shortcut: "G S",
  },
];

export const NAV_SECTIONS: readonly NavSection[] = [
  "PLATFORM",
  "KNOWLEDGE",
  "OPERATIONS",
  "INSIGHTS",
];

// Chapter 12.3 — imposed page titles and subtitles.
export const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/overview": {
    title: "Overview",
    subtitle: "Platform-wide performance at a glance.",
  },
  "/customers": {
    title: "Customers",
    subtitle: "Manage every account, role and access level.",
  },
  "/escalations": {
    title: "Escalations",
    subtitle: "Handoffs from the AI to a manager agent or a human advisor.",
  },
  "/tickets": {
    title: "Tickets",
    subtitle: "Track, assign and resolve every support request.",
  },
  "/knowledge": {
    title: "Knowledge Base",
    subtitle: "Sources the AI agent reads before it answers.",
  },
  "/policies": {
    title: "Policies",
    subtitle: "Governance thresholds enforced at runtime.",
  },
  "/reference": {
    title: "Reference",
    subtitle: "Admin-managed catalogs the agent reads at runtime.",
  },
  "/calls": {
    title: "Calls & Transcripts",
    subtitle: "End-of-call records across all customer sessions.",
  },
  "/advisors": {
    title: "Advisors",
    subtitle: "Availability, workload and performance.",
  },
  "/availability": {
    title: "Availability",
    subtitle: "Coverage across the rota.",
  },
  "/callbacks": {
    title: "Callbacks",
    subtitle: "Scheduled return calls awaiting an advisor.",
  },
  "/decisions": {
    title: "Decisions",
    subtitle: "Every policy verdict and the actions it authorized.",
  },
  "/analytics": {
    title: "Analytics",
    subtitle: "Deep metrics across volume, quality and cost.",
  },
  "/agents": {
    title: "Agents",
    subtitle: "The persona graph and who actually handles traffic.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Workspace configuration and access control.",
  },
};

// Account is now derived from the signed session (see src/lib/api/session.ts).
// The shape is preserved so consuming components did not need restructuring.
export type AccountInfo = {
  name: string;
  role: string;
  email: string;
  initials: string;
};

/** Rendered only before the session resolves, and on the login screen. */
export const ACCOUNT_FALLBACK: AccountInfo = {
  name: "—",
  role: "—",
  email: "",
  initials: "··",
};
