import { getCookie, setCookie } from "@tanstack/react-start/server";
import { serverConfig } from "./config";
import {
  LEGACY_SESSION_COOKIE,
  SESSION_COOKIE,
  signSession,
  verifySession,
  type ClientSession,
} from "./session";

/* ---------- cookie I/O ---------- */

export async function writeSessionCookie(session: ClientSession): Promise<void> {
  setCookie(SESSION_COOKIE, await signSession(session, serverConfig.sessionSecret()), {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: serverConfig.sessionTtlSeconds(),
  });
}

export function clearSessionCookie(): void {
  // Both names: a pre-rebrand cookie must not resurrect a session after logout.
  for (const name of [SESSION_COOKIE, LEGACY_SESSION_COOKIE]) {
    setCookie(name, "", {
      httpOnly: true,
      sameSite: "lax",
      secure: serverConfig.isProduction(),
      path: "/",
      maxAge: 0,
    });
  }
}

export async function readSession(): Promise<ClientSession | null> {
  // The pre-rebrand name is a fallback so the rename is not a logout.
  const raw = getCookie(SESSION_COOKIE) ?? getCookie(LEGACY_SESSION_COOKIE);
  return verifySession(raw, serverConfig.sessionSecret());
}
