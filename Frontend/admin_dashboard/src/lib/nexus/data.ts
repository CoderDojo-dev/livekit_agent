// Part IV reference data. Literal, character for character. Nothing invented.

export const OVERVIEW_STATS = {
  hero: {
    label: "CALL VOLUME",
    value: "48,392",
    delta: 12.4,
    direction: "up" as const,
    polarity: "neutral" as const,
    context: "+1,454.89 today",
  },
  cards: [
    {
      label: "RESOLUTION RATE",
      value: "92.6%",
      delta: 4.1,
      direction: "up" as const,
      good: true,
      context: "+312 resolved today",
      meta: "Target 90.0%",
      icon: "circle-check",
    },
    {
      label: "AVG HANDLE TIME",
      value: "3m 42s",
      delta: -8.3,
      direction: "down" as const,
      good: true,
      context: "\u221222s vs last week",
      meta: "Median 3m 08s",
      icon: "timer",
    },
    {
      label: "ACTIVE ADVISORS",
      value: "146",
      delta: -1.9,
      direction: "down" as const,
      good: false,
      context: "28 away \u00b7 118 online",
      meta: "Across 14 teams",
      icon: "headset",
    },
  ],
};

export const CALL_VOLUME_SERIES = [
  { day: "Mon", current: 3100, previous: 2740 },
  { day: "Tue", current: 3980, previous: 3120 },
  { day: "Wed", current: 4020, previous: 3360 },
  { day: "Thu", current: 5240, previous: 4180 },
  { day: "Fri", current: 5980, previous: 4620 },
  { day: "Sat", current: 5240, previous: 4380 },
  { day: "Sun", current: 5720, previous: 4760 },
];

export const RESOLUTION_SERIES = [
  { week: "W1", ai: 82, advisor: 18 },
  { week: "W2", ai: 88, advisor: 14 },
  { week: "W3", ai: 90, advisor: 15 },
  { week: "W4", ai: 94, advisor: 12 },
];

export const HERO_SPARKLINE = [
  18, 22, 19, 26, 24, 30, 28, 33, 31, 38, 36, 41, 39, 45, 42, 48, 46, 52, 50,
  56, 54, 59, 57, 63, 61, 67, 65, 71, 74, 79,
];

export const BILLING_ACTIVITY = [
  {
    initials: "AO",
    name: "Amara Okafor",
    email: "amara@fintrust.io",
    amount: "$1,299.00",
    status: "paid",
  },
  {
    initials: "RS",
    name: "Ravi Sharma",
    email: "ravi@nexlabs.co",
    amount: "$449.00",
    status: "pending",
  },
  {
    initials: "EV",
    name: "Elena Volkov",
    email: "elena@brightpay.com",
    amount: "$2,150.00",
    status: "paid",
  },
  {
    initials: "BK",
    name: "Boris Kane",
    email: "boris@vaultid.dev",
    amount: "$799.00",
    status: "failed",
  },
];

export const ADVISOR_TEAM = [
  {
    initials: "NR",
    name: "Nadia Rahman",
    presence: "Active now",
    role: "Senior",
    online: true,
  },
  {
    initials: "RS",
    name: "Ravi Sharma",
    presence: "Active now",
    role: "Agent",
    online: true,
  },
  {
    initials: "EV",
    name: "Elena Volkov",
    presence: "Away \u00b7 12m",
    role: "Team Lead",
    online: false,
  },
];

/* ---------------- CUSTOMERS ---------------- */

export const CUSTOMER_STATS = {
  hero: {
    label: "TOTAL USERS",
    value: "18,204",
    delta: 12.4,
    direction: "up" as const,
    context: "+412 this month",
  },
  cards: [
    {
      label: "ACTIVE USERS",
      value: "14,873",
      delta: 8.1,
      direction: "up" as const,
      good: true,
      context: "81.7% of total",
      meta: "Signed in within 30 days",
    },
    {
      label: "PENDING INVITES",
      value: "642",
      delta: 3.2,
      direction: "up" as const,
      good: null,
      context: "+21 this week",
      meta: "Expires after 14 days",
    },
    {
      label: "SUSPENDED",
      value: "128",
      delta: -1.8,
      direction: "down" as const,
      good: true,
      context: "\u22122 this week",
      meta: "0.7% of total",
    },
  ],
};

export type CustomerRow = {
  name: string;
  email: string;
  status: string;
  role: "Admin" | "Advisor" | "Customer";
  lastActive: string;
  age: "hour" | "day" | "week" | "month";
};

export const CUSTOMERS: CustomerRow[] = [
  {
    name: "Emma Morgan",
    email: "emma.morgan@acme.io",
    status: "active",
    role: "Admin",
    lastActive: "2 min ago",
    age: "hour",
  },
  {
    name: "James Turner",
    email: "j.turner@northwind.co",
    status: "invited",
    role: "Advisor",
    lastActive: "1 hr ago",
    age: "day",
  },
  {
    name: "Sofia Lin",
    email: "sofia.lin@brightpath.com",
    status: "suspended",
    role: "Customer",
    lastActive: "3 days ago",
    age: "week",
  },
  {
    name: "Daniel Kim",
    email: "daniel.kim@vertex.io",
    status: "active",
    role: "Advisor",
    lastActive: "8 min ago",
    age: "hour",
  },
  {
    name: "Ravi Anand",
    email: "ravi.anand@quantum.dev",
    status: "inactive",
    role: "Customer",
    lastActive: "2 weeks ago",
    age: "month",
  },
  {
    name: "Maria Costa",
    email: "maria.costa@luma.app",
    status: "invited",
    role: "Customer",
    lastActive: "5 hr ago",
    age: "day",
  },
];

/* ---------------- TICKETS ---------------- */

export const TICKET_STATS = [
  {
    label: "OPEN",
    value: "18",
    delta: 12,
    direction: "up" as const,
    good: false,
    context: "+2 in the last hour",
  },
  {
    label: "IN PROGRESS",
    value: "11",
    delta: 4,
    direction: "up" as const,
    good: null,
    context: "Avg age 4h 12m",
    meta: "9 assigned \u00b7 2 unassigned",
  },
  {
    label: "RESOLVED",
    value: "47",
    delta: 9,
    direction: "up" as const,
    good: true,
    context: "+312 this month",
    meta: "Avg time to resolve 6h 40m",
  },
  {
    label: "CLOSED",
    value: "129",
    delta: -2,
    direction: "down" as const,
    good: null,
    context: "\u22123 this week",
    meta: "Auto-closed after 7 days",
  },
];

export type TicketRow = {
  id: string;
  subject: string;
  customer: string;
  priority: "high" | "medium" | "low";
  status: string;
  advisor: string | null;
  updated: string;
};

export const TICKETS: TicketRow[] = [
  {
    id: "TK-4821",
    subject: "Refund not processed after cancellation",
    customer: "Jordan Meyer",
    priority: "high",
    status: "open",
    advisor: null,
    updated: "2m ago",
  },
  {
    id: "TK-4819",
    subject: "Unable to update billing address",
    customer: "Sara Park",
    priority: "medium",
    status: "in_progress",
    advisor: "AK",
    updated: "18m ago",
  },
  {
    id: "TK-4815",
    subject: "Feature request: dark mode for portal",
    customer: "Dana Liu",
    priority: "low",
    status: "resolved",
    advisor: "RM",
    updated: "1h ago",
  },
  {
    id: "TK-4818",
    subject: "Login loop on mobile Safari",
    customer: "Tomas Green",
    priority: "high",
    status: "open",
    advisor: "NV",
    updated: "3h ago",
  },
  {
    id: "TK-4802",
    subject: "Question about invoice tax breakdown",
    customer: "Mika Rossi",
    priority: "medium",
    status: "closed",
    advisor: "EV",
    updated: "Yesterday",
  },
  {
    id: "TK-4798",
    subject: "API rate limit unexpectedly triggered",
    customer: "Chris Fox",
    priority: "high",
    status: "in_progress",
    advisor: "AK",
    updated: "Yesterday",
  },
];

/* ---------------- CALLS ---------------- */

export type CallRow = {
  id: string;
  name: string;
  uid: string;
  phone: string;
  duration: string;
  day: string;
  time: string;
};

export const CALLS: CallRow[] = [
  {
    id: "c1",
    name: "Jordan Mercer",
    uid: "UID 88213",
    phone: "+1 415 552 0198",
    duration: "04:12",
    day: "Today",
    time: "09:42 AM",
  },
  {
    id: "c2",
    name: "Sana Choudhury",
    uid: "UID 74190",
    phone: "+44 20 7946 1123",
    duration: "07:38",
    day: "Today",
    time: "08:15 AM",
  },
  {
    id: "c3",
    name: "Theo Wallace",
    uid: "UID 65028",
    phone: "+1 212 555 0142",
    duration: "01:54",
    day: "Yesterday",
    time: "05:31 PM",
  },
  {
    id: "c4",
    name: "Elena Marchetti",
    uid: "UID 51837",
    phone: "+39 06 4550 2287",
    duration: "05:26",
    day: "Yesterday",
    time: "02:08 PM",
  },
  {
    id: "c5",
    name: "Rahul Kapoor",
    uid: "UID 43096",
    phone: "+91 22 4890 7712",
    duration: "03:41",
    day: "Mon",
    time: "11:20 AM",
  },
  {
    id: "c6",
    name: "Nadia Karlsson",
    uid: "UID 39471",
    phone: "+46 8 5250 6634",
    duration: "02:17",
    day: "Mon",
    time: "09:03 AM",
  },
];

export const CALL_SUMMARY = [
  "Customer requested help updating the billing address on their premium subscription.",
  "AI agent verified identity and applied the change successfully within the session.",
  "A follow-up email confirmation was scheduled; no escalation to a human advisor needed.",
];

export const CALL_KEYWORDS = [
  "Billing",
  "Subscription",
  "Identity Verification",
  "Address Update",
];

export type TranscriptTurn = {
  at: string;
  speaker: "CUSTOMER" | "AI AGENT" | "ADVISOR";
  text: string;
  entities: string[];
};

export const TRANSCRIPT: TranscriptTurn[] = [
  {
    at: "00:04",
    speaker: "CUSTOMER",
    text: "Hi, I need to update the billing address on my account. I just moved cities.",
    entities: ["billing address"],
  },
  {
    at: "00:11",
    speaker: "AI AGENT",
    text: "Of course, I can help with that. For security I first need to verify your identity. Could you confirm the email on file?",
    entities: ["verify your identity"],
  },
  {
    at: "00:19",
    speaker: "CUSTOMER",
    text: "Sure, it's jordan.mercer@mail.com \u2014 and I'm on the Premium plan.",
    entities: ["Premium plan"],
  },
  {
    at: "00:28",
    speaker: "AI AGENT",
    text: "Perfect, you're verified. What's the new billing address you'd like on file?",
    entities: ["billing address"],
  },
  {
    at: "00:41",
    speaker: "CUSTOMER",
    text: "It's 240 Kearny Street, San Francisco, CA 94108.",
    entities: [],
  },
  {
    at: "00:52",
    speaker: "AI AGENT",
    text: "Done \u2014 your address is updated and I've sent a confirmation email. Anything else I can help with?",
    entities: ["confirmation email"],
  },
];

export const WAVEFORM: number[] = Array.from({ length: 120 }, (_, i) => {
  const base =
    Math.sin(i / 5) * 0.32 + Math.sin(i / 11) * 0.28 + Math.sin(i / 2.3) * 0.18;
  return Math.min(1, Math.max(0.08, Math.abs(base) + 0.12));
});

/* ---------------- CONVERSATIONS ---------------- */

export type ConversationRow = {
  id: string;
  initials: string;
  name: string;
  preview: string;
  at: string;
  live: boolean;
  unread: boolean;
};

export const CONVERSATIONS: ConversationRow[] = [
  {
    id: "v1",
    initials: "EM",
    name: "Elena Moretti",
    preview: "Can you confirm my policy renewal date?",
    at: "2m",
    live: true,
    unread: true,
  },
  {
    id: "v2",
    initials: "MC",
    name: "Marcus Chen",
    preview: "The refund still hasn't appeared in my account.",
    at: "14m",
    live: true,
    unread: true,
  },
  {
    id: "v3",
    initials: "PN",
    name: "Priya Nair",
    preview: "Thanks, that resolved everything perfectly.",
    at: "1h",
    live: false,
    unread: false,
  },
  {
    id: "v4",
    initials: "JB",
    name: "Jon Bauer",
    preview: "I'd like to escalate this to a human advisor.",
    at: "3h",
    live: true,
    unread: false,
  },
  {
    id: "v5",
    initials: "AO",
    name: "Amara Okafor",
    preview: "How do I update my billing information?",
    at: "5h",
    live: false,
    unread: false,
  },
];

export type Bubble = {
  kind: "customer" | "ai" | "advisor" | "system";
  label: string;
  at: string;
  text: string;
  token?: string;
};

export const THREAD: Bubble[] = [
  {
    kind: "customer",
    label: "CUSTOMER",
    at: "10:24",
    text: "Hi, can you confirm my policy renewal date? I want to make sure it doesn't lapse.",
  },
  {
    kind: "ai",
    label: "AI AGENT",
    at: "10:24",
    text: "Your annual policy renews on §March 14, 2025§. Auto-renewal is currently enabled, so no action is required on your part.",
    token: "March 14, 2025",
  },
  {
    kind: "customer",
    label: "CUSTOMER",
    at: "10:26",
    text: "Great. Can I also add my spouse to the policy?",
  },
  {
    kind: "advisor",
    label: "HUMAN ADVISOR \u00b7 DANIEL K.",
    at: "10:28",
    text: "I've stepped in to help with this. Adding a spouse requires identity verification \u2014 I'll email you a secure link now. It typically takes under 5 minutes.",
  },
];

export const INGESTED_FILES = [
  {
    name: "policy_terms_2025.pdf",
    meta: "Mar 12, 2025 \u00b7 2.4 MB",
    status: "indexed",
  },
  {
    name: "faq_knowledge.docx",
    meta: "Mar 14, 2025 \u00b7 860 KB",
    status: "processing",
  },
  {
    name: "legacy_export.txt",
    meta: "Mar 11, 2025 \u00b7 1.1 MB",
    status: "failed",
  },
  {
    name: "onboarding_guide.md",
    meta: "Mar 09, 2025 \u00b7 412 KB",
    status: "indexed",
  },
];

/* ---------------- SECONDARY SCREENS ---------------- */

export const KNOWLEDGE_SOURCES = [
  {
    name: "policy_terms_2025.pdf",
    chunks: "1,204",
    updated: "Mar 12, 2025",
    status: "indexed",
  },
  {
    name: "faq_knowledge.docx",
    chunks: "486",
    updated: "Mar 14, 2025",
    status: "processing",
  },
  {
    name: "onboarding_guide.md",
    chunks: "212",
    updated: "Mar 09, 2025",
    status: "indexed",
  },
  {
    name: "legacy_export.txt",
    chunks: "0",
    updated: "Mar 11, 2025",
    status: "failed",
  },
];

export const POLICIES = [
  {
    name: "Max escalation delay",
    threshold: "120s",
    version: "v3.2.1",
    status: "enabled",
  },
  {
    name: "Identity verification required",
    threshold: "Always",
    version: "v2.0.4",
    status: "enabled",
  },
  {
    name: "Refund approval ceiling",
    threshold: "$500.00",
    version: "v1.7.0",
    status: "enabled",
  },
  {
    name: "Transcript retention",
    threshold: "180d",
    version: "v4.1.2",
    status: "draft",
  },
];

export const RULES = [
  {
    name: "Route billing intents to Finance",
    trigger: "Intent = billing",
    action: "Assign team Finance",
    runs: "1,204",
    status: "enabled",
  },
  {
    name: "Escalate after two failed answers",
    trigger: "AI confidence < 0.4",
    action: "Escalate to advisor",
    runs: "318",
    status: "enabled",
  },
  {
    name: "Auto-close silent tickets",
    trigger: "No reply for 7 days",
    action: "Set status closed",
    runs: "96",
    status: "disabled",
  },
];

export const ADVISORS = [
  {
    initials: "NR",
    name: "Nadia Rahman",
    role: "Senior",
    queue: "3",
    handled: "184",
    status: "online",
  },
  {
    initials: "RS",
    name: "Ravi Sharma",
    role: "Agent",
    queue: "5",
    handled: "142",
    status: "on_call",
  },
  {
    initials: "EV",
    name: "Elena Volkov",
    role: "Team Lead",
    queue: "0",
    handled: "97",
    status: "away",
  },
  {
    initials: "AK",
    name: "Amira Kaya",
    role: "Agent",
    queue: "2",
    handled: "156",
    status: "online",
  },
  {
    initials: "NV",
    name: "Noel Vega",
    role: "Agent",
    queue: "0",
    handled: "88",
    status: "offline",
  },
];

export const CALLBACKS = [
  {
    name: "Jordan Meyer",
    phone: "+1 415 552 0198",
    window: "Today 14:00 \u2013 15:00",
    advisor: "AK",
    status: "queued",
  },
  {
    name: "Sara Park",
    phone: "+1 212 555 0142",
    window: "Today 16:30 \u2013 17:00",
    advisor: null,
    status: "pending",
  },
  {
    name: "Mika Rossi",
    phone: "+39 06 4550 2287",
    window: "Tomorrow 09:00 \u2013 10:00",
    advisor: "EV",
    status: "queued",
  },
];

export const SETTINGS_SECTIONS = [
  {
    name: "General",
    description: "Workspace name, locale, timezone and retention.",
  },
  { name: "Members", description: "People with access to this workspace." },
  { name: "Roles", description: "Permission sets granted to members." },
  { name: "API keys", description: "Server credentials for the public API." },
  {
    name: "Notifications",
    description: "Delivery channels and alert thresholds.",
  },
  { name: "Audit", description: "Every privileged action, immutable." },
  { name: "Danger zone", description: "Irreversible workspace operations." },
];
