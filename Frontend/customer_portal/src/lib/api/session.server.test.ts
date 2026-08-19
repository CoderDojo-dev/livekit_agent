import { beforeEach, describe, expect, it, vi } from "vitest";
import { signSession, type ClientSession } from "./session";

/**
 * Migration regression: the session cookie was renamed from
 * "nexus_portal_session" to "portal_session" (cookbook 20). Existing users
 * carry the old name; this must not log them out, and logout must clear both
 * names so the old cookie cannot resurrect a session.
 */

const cookieJar = new Map<string, string>();

vi.mock("@tanstack/react-start/server", () => ({
  getCookie: (name: string) => cookieJar.get(name) ?? null,
  setCookie: (name: string, value: string, opts: { maxAge?: number }) => {
    if (opts.maxAge === 0) cookieJar.delete(name);
    else cookieJar.set(name, value);
  },
}));

vi.mock("./config", () => ({
  serverConfig: {
    sessionSecret: () => "test-secret-0123456789abcdef",
    sessionTtlSeconds: () => 28800,
    isProduction: () => false,
  },
}));

const SECRET = "test-secret-0123456789abcdef";

function validSession(overrides: Partial<ClientSession> = {}): ClientSession {
  return {
    sub: "user@example.tn",
    role: "client",
    exp: Math.floor(Date.now() / 1000) + 3600,
    token: "bearer-token",
    ...overrides,
  };
}

async function signed(session: ClientSession): Promise<string> {
  return signSession(session, SECRET);
}

describe("session cookie migration", () => {
  beforeEach(() => {
    cookieJar.clear();
  });

  it("authenticates a user who still carries only the legacy cookie name", async () => {
    const session = validSession();
    cookieJar.set("nexus_portal_session", await signed(session));

    const { readSession } = await import("./session.server");
    const result = await readSession();

    expect(result?.sub).toBe(session.sub);
    expect(result?.token).toBe(session.token);
  });

  it("prefers the new cookie name when both are present", async () => {
    const legacy = validSession({ sub: "legacy@example.tn" });
    const current = validSession({ sub: "current@example.tn" });
    cookieJar.set("nexus_portal_session", await signed(legacy));
    cookieJar.set("portal_session", await signed(current));

    const { readSession } = await import("./session.server");
    const result = await readSession();

    expect(result?.sub).toBe("current@example.tn");
  });

  it("rejects an invalid legacy cookie instead of trusting the name", async () => {
    cookieJar.set("nexus_portal_session", "forged.payload.signature");

    const { readSession } = await import("./session.server");
    expect(await readSession()).toBeNull();
  });

  it("clears both cookie names on logout so the legacy cookie cannot resurrect a session", async () => {
    const session = validSession();
    const value = await signed(session);
    cookieJar.set("nexus_portal_session", value);
    cookieJar.set("portal_session", value);

    const { clearSessionCookie } = await import("./session.server");
    clearSessionCookie();

    expect(cookieJar.has("nexus_portal_session")).toBe(false);
    expect(cookieJar.has("portal_session")).toBe(false);
  });
});
