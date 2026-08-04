// Part IV reference data. Literal, character for character. Nothing invented.

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
