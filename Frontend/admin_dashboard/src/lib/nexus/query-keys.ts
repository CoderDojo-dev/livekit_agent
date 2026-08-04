/**
 * Central query-key factory. Every cookbook adds its keys here, never inline, so that
 * invalidation after a mutation is a one-liner and cache collisions are impossible.
 */
export const queryKeys = {
  session: ["session"] as const,
  health: ["health"] as const,

  advisors: {
    all: ["advisors"] as const,
    list: (includeInactive: boolean) => ["advisors", "list", { includeInactive }] as const,
    onCall: ["advisors", "on-call"] as const,
    coverage: (days: number) => ["advisors", "coverage", { days }] as const,
    schedule: (advisorId: string) => ["advisors", advisorId, "schedule"] as const,
    timeOff: (advisorId: string, upcomingOnly: boolean) =>
      ["advisors", advisorId, "time-off", { upcomingOnly }] as const,
  },

  callbacks: {
    all: ["callbacks"] as const,
    list: (status: string, overdueOnly: boolean) =>
      ["callbacks", "list", { status, overdueOnly }] as const,
    stats: ["callbacks", "stats"] as const,
    slots: (day: string | undefined) => ["callbacks", "slots", { day }] as const,
  },

  sessions: {
    detail: (sessionId: string) => ["sessions", sessionId] as const,
  },

  customers: {
    profile360: (customerId: string) => ["customers", customerId, "360"] as const,
  },

  supervision: {
    escalations: (status: string) => ["escalations", { status }] as const,
    verdicts: (sessionId: string) => ["verdicts", { sessionId }] as const,
    actions: (status: string) => ["actions", { status }] as const,
    kpis: ["kpis"] as const,
    systemOverview: ["system", "overview"] as const,
    telemetryTimeline: ["telemetry", "timeline"] as const,
    businessRules: ["reference", "business-rules"] as const,
    auditVerify: ["audit", "verify"] as const,
    integrity: ["jobs", "integrity"] as const,
  },
} as const;

/* Feature 2 — availability. Standalone export, same pattern as Feature 1's advisorKeys. */
export const availabilityKeys = {
  all: ["availability"] as const,
  coverage: (days: number) => ["availability", "coverage", { days }] as const,
  week: (advisorId: string) => ["availability", "week", advisorId] as const,
};

/* Feature 3 — callback queue. Standalone export. Mutations invalidate callbackKeys.all AND
 * callbackKeys.stats(); completing a callback changes both the rows and the counters. */
export const callbackKeys = {
  all: ["callbacks"] as const,
  list: (status: string, overdueOnly: boolean, limit: number) =>
    ["callbacks", "list", status, overdueOnly, limit] as const,
  stats: () => ["callbacks", "stats"] as const,
};

/* Feature 4 — call history. Standalone export. Read-only. limit is in the key because
 * "Load more" grows the page size; omitting it would serve a stale short page from cache. */
export const callKeys = {
  all: ["calls"] as const,
  list: (search: string, disposition: string, limit: number) =>
    ["calls", "list", search, disposition, limit] as const,
  detail: (sessionId: string) => ["calls", "detail", sessionId] as const,
};

/* Feature 5 - ticket mirror. Standalone export, read-only. limit is in the key because
 * "Load more" grows the page size; filters are in the key so each filtered view is its own cache. */
export const ticketKeys = {
  all: ["tickets"] as const,
  list: (status: string, category: string, priority: string, search: string, limit: number) =>
    ["tickets", "list", status, category, priority, search, limit] as const,
};

/* Feature 6 — knowledge base. Standalone export. Mutations invalidate documents() AND health():
 * an upload changes `points` too, so a stale health strip after a mutation is the kind of quiet
 * inconsistency this series eliminates. The retrieval probe is deliberately NOT keyed — it is a
 * user-triggered query whose results must never be cached or replayed, and must never invalidate
 * the inventory. */
export const knowledgeKeys = {
  all: ["knowledge"] as const,
  documents: () => [...knowledgeKeys.all, "documents"] as const,
  health: () => [...knowledgeKeys.all, "health"] as const,
};

/* Feature 7 — policies. Read-only registry; no mutations, so no invalidation anywhere. */
export const policyKeys = {
  all: ["policies"] as const,
  rules: () => [...policyKeys.all, "rules"] as const,
};
