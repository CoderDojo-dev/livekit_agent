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
  18, 22, 19, 26, 24, 30, 28, 33, 31, 38, 36, 41, 39, 45, 42, 48, 46, 52, 50, 56, 54, 59, 57, 63,
  61, 67, 65, 71, 74, 79,
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

/* ---------------- SECONDARY SCREENS ---------------- */

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
