import { useLoaderData } from "@tanstack/react-router";
import type { ClientSession } from "@/lib/api/session";

/**
 * The layout route's loader data (returned by /_portal beforeLoad: { session }).
 *
 * The router types resolve the layout's loader data as `never` in the installed
 * version, so the shape is asserted here once instead of in every screen. The
 * runtime guarantee is real: /_portal beforeLoad redirects to /login when the
 * session cookie is missing or expired, so a child screen only ever renders
 * with a session (or with `undefined` while the redirect is in flight).
 */
export function usePortalSession(): ClientSession | undefined {
  const data = useLoaderData({ from: "/_portal" }) as { session: ClientSession } | undefined;
  return data?.session;
}
