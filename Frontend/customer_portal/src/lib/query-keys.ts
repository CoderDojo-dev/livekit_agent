/**
 * lib/query-keys.ts — client-side cache keys for the customer portal.
 *
 * Every key carries the signed-in customer id so a different account can never
 * see another account's cached rows. The id is a cache key only: it is never
 * sent to business-api, which derives customer_id from the bearer token.
 */
export const qk = {
  profileDetail: (cid: string) => ["me", cid, "profile-detail"] as const,
  profile360: (cid: string) => ["me", cid, "profile"] as const,
  sessions: (cid: string) => ["me", cid, "sessions"] as const,
  conversations: (cid: string, limit: number, offset: number) =>
    ["me", cid, "conversations", limit, offset] as const,
  conversation: (cid: string, id: string) => ["me", cid, "conversation", id] as const,
  requests: (cid: string, status: string | undefined, limit: number, offset: number) =>
    ["me", cid, "requests", status ?? "all", limit, offset] as const,
  billing: (cid: string, limit: number, offset: number) =>
    ["me", cid, "billing", limit, offset] as const,
  balance: (cid: string) => ["me", cid, "balance"] as const,
  notifications: (cid: string, limit: number, offset: number) =>
    ["me", cid, "notifications", limit, offset] as const,
  callbacks: (cid: string, limit: number, offset: number) =>
    ["me", cid, "callbacks", limit, offset] as const,
};
