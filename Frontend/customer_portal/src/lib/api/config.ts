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

  /** HMAC key for the session cookie. Generate: openssl rand -hex 32 */
  sessionSecret: () => required("PORTAL_SESSION_SECRET"),

  /** Session lifetime in seconds. Default 8 h. */
  sessionTtlSeconds: () => Number(optional("PORTAL_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  isProduction: () => process.env["NODE_ENV"] === "production",
} as const;
