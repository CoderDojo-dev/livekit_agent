export const SESSION_COOKIE = "nexus_portal_session";

/** The only role a customer's portal session ever carries. Rank 0: it can pass every client gate. */
export type ClientRole = "client";

export const CLIENT_RANK: Record<ClientRole, number> = { client: 0 };

export type ClientSession = {
  /** Subject — the customer's email. */
  sub: string;
  role: ClientRole;
  /** Expiry, epoch seconds. */
  exp: number;
  /**
   * Opaque bearer token issued by POST /api/v1/auth/login. Sealed inside the httpOnly,
   * HMAC-signed cookie, so it is never readable by client JavaScript and cannot be forged.
   * business-api revalidates it against auth.portal_sessions on every request.
   */
  token: string;
  /**
   * crm.customers.customer_id, returned by /auth/login and /auth/signup.
   * Never sent to business-api: /me/* routes derive it from the bearer token.
   * Held only so the UI can key client-side caches per customer.
   */
  customerId?: string;
};

/* ---------- base64url (no padding) ---------- */

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/* ---------- HMAC-SHA-256 via Web Crypto (Node 18+ and Cloudflare Workers) ---------- */

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

/** Constant-time comparison — avoids leaking signature bytes through timing. */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/**
 * HMAC-SHA-256 sign. `secret` is supplied by the server-only caller so this module stays free of
 * server-only imports and remains importable from the client bundle.
 */
export async function signSession(session: ClientSession, secret: string): Promise<string> {
  const payload = toBase64Url(new TextEncoder().encode(JSON.stringify(session)));
  const signature = await crypto.subtle.sign(
    "HMAC",
    await hmacKey(secret),
    new TextEncoder().encode(payload),
  );
  return `${payload}.${toBase64Url(new Uint8Array(signature))}`;
}

export async function verifySession(
  token: string | undefined,
  secret: string,
): Promise<ClientSession | null> {
  if (!token) return null;

  const separator = token.lastIndexOf(".");
  if (separator <= 0) return null;

  const payload = token.slice(0, separator);
  const signature = token.slice(separator + 1);

  const expected = toBase64Url(
    new Uint8Array(
      await crypto.subtle.sign("HMAC", await hmacKey(secret), new TextEncoder().encode(payload)),
    ),
  );
  if (!timingSafeEqual(signature, expected)) return null;

  try {
    const session = JSON.parse(new TextDecoder().decode(fromBase64Url(payload))) as ClientSession;
    if (typeof session.exp !== "number" || session.exp * 1000 < Date.now()) return null;
    if (session.role !== "client") return null;
    if (session.customerId !== undefined && typeof session.customerId !== "string") return null;
    return session;
  } catch {
    return null;
  }
}
