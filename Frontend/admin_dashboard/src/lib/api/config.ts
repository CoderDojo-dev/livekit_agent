/**
 * Server-only configuration. Never imported from a component.
 *
 * Deliberately NOT prefixed with VITE_: the Lovable vite preset injects VITE_* into the client
 * bundle, and the backend URL and session secret must never reach the browser.
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
  sessionSecret: () => required("ADMIN_SESSION_SECRET"),

  /** Seeded admin credentials — see §8.1, this is the deliberate stop-gap. */
  adminEmail: () => required("ADMIN_EMAIL"),
  adminPassword: () => required("ADMIN_PASSWORD"),

  /** Backend role granted on login. One of: conseiller | superviseur | administrateur */
  adminRole: () => optional("ADMIN_ROLE", "administrateur"),

  /** Session lifetime in seconds. Default 8 h — one shift. */
  sessionTtlSeconds: () => Number(optional("ADMIN_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  isProduction: () => process.env["NODE_ENV"] === "production",
} as const;
