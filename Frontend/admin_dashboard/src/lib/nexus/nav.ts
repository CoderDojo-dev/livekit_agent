// Source of truth for primary navigation and its visibility requirements.
import type { AdminSession, BackendRole } from "@/lib/api/session";
import { hasRank } from "@/lib/api/session";
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
  Send,
  BarChart3,
  Scale,
  Settings,
  Bot,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export type NavSection = "PLATFORM" | "KNOWLEDGE" | "OPERATIONS" | "INSIGHTS";

export type NavItem = {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  section: NavSection;
  shortcut: string;
  minimumRole?: BackendRole;
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
    minimumRole: "administrateur",
  },
  {
    id: "reference",
    label: "Reference",
    href: "/reference",
    icon: GitBranch,
    section: "KNOWLEDGE",
    shortcut: "G R",
    minimumRole: "administrateur",
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
  },
  {
    id: "notifications",
    label: "Notifications",
    href: "/notifications",
    icon: Send,
    section: "OPERATIONS",
    shortcut: "G M",
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
    id: "audit",
    label: "Audit",
    href: "/audit",
    icon: ShieldCheck,
    section: "INSIGHTS",
    shortcut: "G U",
    minimumRole: "administrateur",
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

export function canSeeNavItem(item: NavItem, session: Pick<AdminSession, "role"> | null): boolean {
  return item.minimumRole === undefined || (session !== null && hasRank(session, item.minimumRole));
}

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
    subtitle: "Observed support KPIs, advisor availability and reported services.",
  },
  "/customers": {
    title: "Customers",
    subtitle: "Search CRM customer records and open customer details.",
  },
  "/escalations": {
    title: "Escalations",
    subtitle: "Handoffs from the AI to a manager agent or a human advisor.",
  },
  "/tickets": {
    title: "Tickets",
    subtitle: "Mirrored view of support tickets, read-only.",
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
    subtitle: "Registry, availability and capacity.",
  },
  "/availability": {
    title: "Availability",
    subtitle: "Coverage across the rota.",
  },
  "/callbacks": {
    title: "Callbacks",
    subtitle: "Scheduled return calls awaiting an advisor.",
  },
  "/notifications": {
    title: "Notifications",
    subtitle: "Written confirmations the platform attempted, and how they landed.",
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
    subtitle: "Review the agent catalog and observed activity.",
  },
  "/audit": {
    title: "Audit",
    subtitle: "Append-only ledger, integrity verification and retention operations.",
  },
  "/settings": {
    title: "Settings",
    subtitle: "Account and session security.",
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
