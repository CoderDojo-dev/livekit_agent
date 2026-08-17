import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { clearSessionCookie } from "./session.server";
import { authedMiddleware } from "./middleware";

/**
 * POST /api/v1/auth/password
 *
 * Verified backend behaviour (portal_auth.change_password):
 *  - wrong current password        -> invalid_credentials -> 401
 *  - fewer than 10 characters      -> weak_password       -> 400
 *  - same as the current password  -> weak_password       -> 400
 *  - on success: rotates the hash, stamps password_changed_at, and calls
 *    revoke_all() — THIS SESSION INCLUDED.
 *
 * Because the bearer token dies with the change, the cookie is cleared here and
 * the caller must send the user to /login.
 */
export const changePassword = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      current_password: z.string().min(1),
      new_password: z.string().min(10),
    }),
  )
  .handler(async ({ data }) => {
    const payload = await businessApi<{ revoked_sessions: number }>("/api/v1/auth/password", {
      method: "POST",
      body: data,
    });
    await clearSessionCookie();
    return payload;
  });

/**
 * POST /api/v1/auth/sessions/revoke-all
 * revoke_all() also kills the caller's own session, so the cookie goes too.
 */
export const revokeAllSessions = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async () => {
    const payload = await businessApi<{ revoked: number }>("/api/v1/auth/sessions/revoke-all", {
      method: "POST",
    });
    await clearSessionCookie();
    return payload;
  });
