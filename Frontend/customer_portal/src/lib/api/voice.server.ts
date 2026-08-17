import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { authedMiddleware } from "./middleware";
import { getSession } from "./auth.server";
import { fetchProfileDetail } from "./me.server";

export type VoiceGrant = {
  token: string;
  url: string;
  room: string;
  agentName: string | null;
  /** Display name for the customer's own turns in the transcript. */
  participantName: string;
};

/**
 * Mint a LiveKit join token for the signed-in customer.
 *
 * Why this is a server function and not a browser fetch:
 *   - token-service POST /token has no authentication and trusts the room and
 *     identity it is given, so only the server may choose them;
 *   - the identity is derived from the session cookie (customer_id), which the
 *     browser cannot forge (HMAC-signed, httpOnly);
 *   - the token-service origin never reaches the client bundle, matching the
 *     BUSINESS_API_URL discipline documented in .env.example.
 *
 * The returned token is short-lived by design (15 minutes, set by the token
 * service) and is only ever used to join one room.
 */
export const createVoiceGrant = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<VoiceGrant> => {
    const session = await getSession();
    if (!session?.customerId) {
      throw new ApiError(401, "No customer session.", "/token");
    }

    // The agent needs a subscriber to resolve. Read it from the client-scoped
    // profile route, never from the browser.
    const profile = await fetchProfileDetail();

    // Stable prefix + random suffix: one room per call, never reused, and never
    // guessable by another customer.
    const suffix = crypto.randomUUID().slice(0, 8);
    const room = `portal-${session.customerId}-${suffix}`;
    const identity = `customer-${session.customerId}`;
    const participantName = profile.full_name ?? profile.first_name ?? "You";

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

    try {
      const response = await fetch(`${serverConfig.tokenServiceUrl()}/token`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          // Proves this /token call comes from the portal server, which is the
          // only reason token-service will trust caller_msisdn. Never reaches
          // the browser: this handler runs server-side only.
          ...(serverConfig.internalApiKey()
            ? { "x-internal-api-key": serverConfig.internalApiKey() }
            : {}),
        },
        signal: controller.signal,
        body: JSON.stringify({
          room,
          identity,
          name: participantName,
          // Only meaningful once the token service accepts it (Cookbook 5 §5.2,
          // Option A). Older builds ignore the field and fall back to
          // PILOT_MSISDN, so sending it is always safe.
          caller_msisdn: profile.msisdn ?? null,
        }),
      });

      if (!response.ok) {
        throw new ApiError(response.status, await response.text(), "/token");
      }

      const payload = (await response.json()) as {
        token: string;
        url: string;
        room: string;
        agent_name?: string | null;
      };

      if (!payload.token || !payload.url) {
        throw new ApiError(502, "Token service returned an incomplete grant.", "/token");
      }

      return {
        token: payload.token,
        url: payload.url,
        room: payload.room,
        agentName: payload.agent_name ?? null,
        participantName,
      };
    } finally {
      clearTimeout(timer);
    }
  });

/** Fire-and-forget browser telemetry, proxied so the origin stays server-side. */
export const reportVoiceEvent = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .validator((input: { event: string; details?: Record<string, unknown> }) => input)
  .handler(async ({ data }) => {
    try {
      await fetch(`${serverConfig.tokenServiceUrl()}/client-events`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ event: data.event, details: data.details ?? {} }),
      });
    } catch {
      // Observability must never block or fail the call path — same rule the
      // client-widget and frontend_events.py both follow.
    }
    return { ok: true } as const;
  });
