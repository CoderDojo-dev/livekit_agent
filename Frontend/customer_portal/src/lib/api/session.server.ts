import { getCookie, setCookie } from "@tanstack/react-start/server";
import { serverConfig } from "./config";
import { SESSION_COOKIE, signSession, verifySession, type ClientSession } from "./session";

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
  setCookie(SESSION_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: serverConfig.isProduction(),
    path: "/",
    maxAge: 0,
  });
}

export async function readSession(): Promise<ClientSession | null> {
  return verifySession(getCookie(SESSION_COOKIE), serverConfig.sessionSecret());
}
