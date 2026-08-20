/**
 * Central query-key factory. Every cookbook adds its keys here, never inline, so that
 * invalidation after a mutation is a one-liner and cache collisions are impossible.
 */
export const queryKeys = {
  session: ["session"] as const,
  health: ["health"] as const,
  serviceHealth: ["system", "health"] as const,

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

/* Feature 2 â€” availability. Standalone export, same pattern as Feature 1's advisorKeys. */
export const availabilityKeys = {
  all: ["availability"] as const,
  coverage: (days: number) => ["availability", "coverage", { days }] as const,
  week: (advisorId: string) => ["availability", "week", advisorId] as const,
};

/* Feature 3 â€” callback queue. Standalone export. Mutations invalidate callbackKeys.all AND
 * callbackKeys.stats(); completing a callback changes both the rows and the counters. */
export const callbackKeys = {
  all: ["callbacks"] as const,
  list: (status: string, overdueOnly: boolean, limit: number) =>
    ["callbacks", "list", status, overdueOnly, limit] as const,
  stats: () => ["callbacks", "stats"] as const,
};

/* Feature 4 â€” call history. Standalone export. Read-only. limit is in the key because
 * "Load more" grows the page size; omitting it would serve a stale short page from cache. */
export const callKeys = {
  all: ["calls"] as const,
  list: (search: string, disposition: string, limit: number, offset: number) =>
    ["calls", "list", search, disposition, limit, offset] as const,
  detail: (sessionId: string) => ["calls", "detail", sessionId] as const,
};

/* Feature 5 - ticket mirror. Standalone export, read-only. limit is in the key because
 * "Load more" grows the page size; filters are in the key so each filtered view is its own cache. */
export const ticketKeys = {
  all: ["tickets"] as const,
  /** offset joined limit when "Load more" was replaced by real pagination: each page is now its
   *  own cache entry, so stepping back to page 1 is instant instead of a refetch. */
  list: (
    status: string,
    category: string,
    priority: string,
    search: string,
    limit: number,
    offset: number,
  ) => ["tickets", "list", status, category, priority, search, limit, offset] as const,
};

/* Feature 18 â€” notification send log. Standalone export, read-only. channel + status are in
 * the key so each filtered view is its own cache; limit is in the key for "Load more". */
export const notificationKeys = {
  all: ["notifications"] as const,
  list: (channel: string, status: string, limit: number, offset: number) =>
    ["notifications", "list", channel, status, limit, offset] as const,
};

/* Feature 6 â€” knowledge base. Standalone export. Mutations invalidate documents() AND health():
 * an upload changes `points` too, so a stale health strip after a mutation is the kind of quiet
 * inconsistency this series eliminates. The retrieval probe is deliberately NOT keyed â€” it is a
 * user-triggered query whose results must never be cached or replayed, and must never invalidate
 * the inventory. */
export const knowledgeKeys = {
  all: ["knowledge"] as const,
  documents: () => [...knowledgeKeys.all, "documents"] as const,
  health: () => [...knowledgeKeys.all, "health"] as const,
};

/* Feature 7 â€” policies. Read-only registry; no mutations, so no invalidation anywhere. */
export const policyKeys = {
  all: ["policies"] as const,
  rules: () => [...policyKeys.all, "rules"] as const,
};

/* Feature 13 â€” escalations. Read-only; scope is in the key so Open/All are separate caches. */
export const escalationKeys = {
  all: ["escalations"] as const,
  list: (scope: string) => ["escalations", "list", scope] as const,
};

/* Feature 8 â€” decisions & actions ledger. Read-only. verdict is in the key so each filtered
 * view is its own cache; the header distribution is a separate, static telemetry read. */
export const decisionKeys = {
  all: ["decisions"] as const,
  list: (verdict: string) => ["decisions", "list", verdict] as const,
  distribution: () => [...decisionKeys.all, "distribution"] as const,
};

/* Feature 9 â€” KPIs & analytics. trend is keyed on days so switching the window is a cache hit
 * on return, consistent with availabilityKeys. */
export const analyticsKeys = {
  all: ["analytics"] as const,
  kpis: () => [...analyticsKeys.all, "kpis"] as const,
  system: () => [...analyticsKeys.all, "system"] as const,
  verdicts: () => [...analyticsKeys.all, "verdicts"] as const,
  trend: (days: number) => [...analyticsKeys.all, "trend", days] as const,
};

/* Feature 10 â€” audit ledger browse. Only the list is a query; verify, integrity and retention
 * are mutations and hold no cache key. */
export const auditKeys = {
  all: ["audit"] as const,
  entries: (eventType?: string) => [...auditKeys.all, "entries", eventType ?? ""] as const,
};

/* Feature 11 â€” customer registry & 360. Every filter is part of the list key, so paging and
 * searching cache independently and going back a page is instant. */
export const customerKeys = {
  all: ["customers"] as const,
  /** Status distribution for the header card. Independent of the list's filters. */
  mix: () => ["customers", "mix"] as const,
  list: (search: string, status: string, limit: number, offset: number) =>
    ["customers", "list", search, status, limit, offset] as const,
  detail: (customerId: string) => ["customers", "detail", customerId] as const,
  ledger: (customerId: string) => ["customers", "ledger", customerId] as const,
  serviceActions: (customerId: string) => ["customers", "serviceActions", customerId] as const,
};

/* Feature 12 â€” persona graph & activity. The window is part of the key so
 * switching 7d/14d/30d refetches under a distinct cache entry. */
export const agentKeys = {
  all: ["agents"] as const,
  activity: (days: number) => ["agents", "activity", days] as const,
};

/* Feature 14 â€” reference catalogs. Catalog + search are both in the key so
 * switching tabs or typing never serves a stale term against another table. */
export const referenceKeys = {
  all: ["reference"] as const,
  catalog: (catalog: string, search: string) => ["reference", "catalog", catalog, search] as const,
};

/* Sidebar badge counts. One key, one request, shared by the desktop rail and the mobile sheet
 * (both render <SidebarContent>, so without a shared key they would fetch twice on mobile). */
export const navKeys = {
  all: ["nav"] as const,
  counts: () => ["nav", "counts"] as const,
};
