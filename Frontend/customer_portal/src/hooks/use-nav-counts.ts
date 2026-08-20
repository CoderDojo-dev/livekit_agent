import { useQuery } from "@tanstack/react-query";
import { usePortalSession } from "@/lib/use-portal-session";
import { qk } from "@/lib/query-keys";
import { fetchConversations } from "@/lib/api/activity.server";
import { fetchRequests } from "@/lib/api/requests.server";
import { isActiveRequest } from "@/lib/request-status";

/**
 * hooks/use-nav-counts.ts — the numbers the rail and the mobile bar carry.
 *
 * Every count is a real server number, and every query here reuses a key an
 * existing screen already owns, so the rail costs nothing on the screen the
 * number belongs to and one cached read anywhere else:
 *
 *   conversations -> qk.conversations(cid, 1, 0)          (Activity's hero query)
 *   requests      -> qk.requests(cid, undefined, 50, 0)   (the Requests list query)
 *
 * The conversation count is the endpoint's own `total`. The active-request
 * count is computed over the same 50-row window the Requests screen filters,
 * paginates and labels from — sharing that window is what keeps the badge and
 * the page from ever disagreeing, which matters more here than counting past
 * the fiftieth ticket.
 *
 * A count is `null` until it is known. Rendering 0 while a request is in
 * flight would state something false about the account.
 */
export type NavCounts = Record<string, number | null>;

export function useNavCounts(): NavCounts {
  const session = usePortalSession();
  const cid = session?.customerId ?? "unknown";
  const enabled = Boolean(session?.customerId);

  const conversations = useQuery({
    queryKey: qk.conversations(cid, 1, 0),
    queryFn: () => fetchConversations({ data: { limit: 1, offset: 0 } }),
    enabled,
    staleTime: 30_000,
  });

  const requests = useQuery({
    queryKey: qk.requests(cid, undefined, 50, 0),
    queryFn: () => fetchRequests({ data: { status: undefined, limit: 50, offset: 0 } }),
    enabled,
    staleTime: 30_000,
  });

  const activeRequests = requests.data
    ? requests.data.items.filter((item) => isActiveRequest(item.status)).length
    : null;

  return {
    "/activity": conversations.data?.total ?? null,
    "/requests": activeRequests,
  };
}
