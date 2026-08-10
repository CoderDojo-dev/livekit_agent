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

  /*
   * There is deliberately no adminEmail / adminPassword / adminRole here.
   *
   * Before P0-1 this process compared the submitted credentials against ADMIN_EMAIL and
   * ADMIN_PASSWORD and then minted a session with ADMIN_ROLE (defaulting to administrateur).
   * Since P0-1, login POSTs to /api/v1/auth/login and business-api verifies a scrypt hash in
   * auth.portal_accounts; the role in the cookie is the role the BACKEND returned. This process
   * no longer holds, compares, or can leak a password, and it cannot choose a role.
   *
   * ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_ROLE still exist — they are read by
   * business_api.seed_admin to bootstrap that one staff row. They are backend variables. They
   * are not this application's business, and requiring them here only forced operators to
   * invent placeholder values to make the app boot.
   */

  /** Session lifetime in seconds. Default 8 h — one shift. */
  sessionTtlSeconds: () => Number(optional("ADMIN_SESSION_TTL", "28800")),

  /** Upstream timeout in ms. */
  requestTimeoutMs: () => Number(optional("BUSINESS_API_TIMEOUT_MS", "15000")),

  isProduction: () => process.env["NODE_ENV"] === "production",
} as const;
