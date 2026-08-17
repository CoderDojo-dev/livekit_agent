/**
 * Server-only configuration. Never imported from a component.
 *
 * Deliberately NOT prefixed with VITE_: the Lovable vite preset injects VITE_* into the client
 * bundle, and the backend URL and session secret must never reach the browser.
 *
 * Mirrors Frontend/admin_dashboard/src/lib/api/config.ts on purpose - one identity layer, two
 * front ends, the same shape on both sides.
 */

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Copy .env.example to .env and fill it in.`,
    );
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] || fallback;
}

export const serverConfig = {
  /** business-api origin. Docker: http://business-api:8108 */
  businessApiUrl: () => optional("BUSINESS_API_URL", "http://localhost:8108").replace(/\/$/, ""),

  /** token-service origin. Server-only, exactly like BUSINESS_API_URL: the
   * browser must never learn it, because POST /token is unauthenticated and
   * accepts a caller-chosen room and identity. */
  tokenServiceUrl: () => optional("TOKEN_SERVICE_URL", "http://localhost:8107").replace(/\/$/, ""),

  /** HMAC key for the session cookie. Generate: openssl rand -hex 32 */
  sessionSecret: () => required("PORTAL_SESSION_SECRET"),

  /** Session lifetime in seconds. Default 8 h. */
  sessionTtlSeconds: () => Number(optional("PORTAL_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  /** Server-only. Empty string means "not configured", which downgrades the
   *  grant to PILOT_MSISDN rather than failing the call. */
  internalApiKey: () => (process.env["INTERNAL_API_KEY"] ?? "").trim(),

  isProduction: () => process.env["NODE_ENV"] === "production",
} as const;
