import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { clearSessionCookie, readSession, writeSessionCookie } from "./session.server";
import type { AdminSession, BackendRole } from "./session";

/** Equalises response time so a wrong email and a wrong password are indistinguishable. */
async function constantTimeDelay(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 120));
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<AdminSession | null> => readSession(),
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }
    return { email: data.email.trim().toLowerCase(), password: data.password };
  })
  .handler(async ({ data }): Promise<AdminSession> => {
    await constantTimeDelay();

    const expectedEmail = serverConfig.adminEmail().trim().toLowerCase();
    const expectedPassword = serverConfig.adminPassword();

    if (data.email !== expectedEmail || data.password !== expectedPassword) {
      throw new ApiError(401, "Incorrect email or password", "login");
    }

    const session: AdminSession = {
      sub: expectedEmail,
      role: serverConfig.adminRole() as BackendRole,
      exp: Math.floor(Date.now() / 1000) + serverConfig.sessionTtlSeconds(),
    };

    await writeSessionCookie(session);
    return session;
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  clearSessionCookie();
});
