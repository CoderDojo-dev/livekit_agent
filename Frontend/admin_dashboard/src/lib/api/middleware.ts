import { createMiddleware } from "@tanstack/react-start";
import { ApiError } from "./errors";
import { readSession } from "./session.server";
import { hasRank, type AdminSession, type BackendRole } from "./session";

/**
 * THE security boundary.
 *
 * Per the TanStack Start authentication guide, server functions are reachable independently of
 * the route that renders them, so a beforeLoad guard is NOT sufficient. Attach this middleware
 * to every server function that touches backend data.
 */
export const authedMiddleware = createMiddleware().server(async ({ next }) => {
  const session = await readSession();
  if (!session) {
    throw new ApiError(401, "Not authenticated", "session");
  }
  return next({ context: { session } });
});

/**
 * Role-gated variant. Mirrors require_role() in business_api/security.py so the UI fails at the
 * edge with the same verdict the backend would return, instead of making a doomed round trip.
 *
 * Usage:
 *   createServerFn({ method: "POST" })
 *     .middleware([requireRole("administrateur")])
 *     .handler(async ({ context }) => { ... })
 */
export function requireRole(minimum: BackendRole) {
  return createMiddleware().server(async ({ next }) => {
    const session = await readSession();
    if (!session) throw new ApiError(401, "Not authenticated", "session");
    if (!hasRank(session, minimum)) {
      throw new ApiError(403, `requires role >= ${minimum}`, "session");
    }
    return next({ context: { session } });
  });
}

export type AuthedContext = { session: AdminSession };
