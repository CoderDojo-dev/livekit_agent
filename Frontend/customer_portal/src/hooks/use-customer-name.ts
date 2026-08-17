import { useQuery } from "@tanstack/react-query";
import { fetchProfileDetail } from "@/lib/api/me.server";

/**
 * The customer's display name for the transcript.
 * The same ["me", "profile", "detail"] query the topbar already runs, so this
 * is free; "You" until it resolves.
 */
export function useCustomerName(): string {
  const profile = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });
  return profile.data?.full_name ?? "You";
}
