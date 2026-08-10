import { createMiddleware } from "@tanstack/react-start";
import { ApiError } from "./errors";
import { readSession } from "./session.server";

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
