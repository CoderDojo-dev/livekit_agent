import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError } from "./errors";
import { businessApi } from "./business-api";
import { clearSessionCookie, readSession, writeSessionCookie } from "./session.server";
import type { ClientSession } from "./session";

type LoginResponse = {
  token: string;
  expires_at: string;
  email: string;
  role: string;
  kind: string;
};

/**
 * Credentials are verified by business-api against a scrypt hash in auth.portal_accounts.
 * This process no longer holds, compares, or can leak a password.
 */
async function postCredential<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(`${serverConfig.businessApiUrl()}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (cause) {
    const timedOut = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      timedOut ? 504 : 503,
      timedOut ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  const raw = await response.text();

  if (!response.ok) {
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* non-JSON error body — keep the raw text */
    }
    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError(502, "business-api returned a malformed JSON body", path);
  }
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<ClientSession | null> => readSession(),
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }
    return { email: data.email.trim().toLowerCase(), password: data.password };
  })
  .handler(async ({ data }): Promise<ClientSession> => {
    const result = await postCredential<LoginResponse>("/api/v1/auth/login", {
      email: data.email,
      password: data.password,
    });

    const session: ClientSession = {
      sub: result.email,
      role: "client",
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
    };

    await writeSessionCookie(session);
    return session;
  });

type SignupResponse = {
  email: string;
  kind: string;
  role: string;
  token: string;
  expires_at: string;
};

export const signup = createServerFn({ method: "POST" })
  .inputValidator(
    (data: { email: string; password: string; cin: string; phone?: string; region?: string }) => {
      if (
        typeof data?.email !== "string" ||
        typeof data?.password !== "string" ||
        typeof data?.cin !== "string"
      ) {
        throw new ApiError(400, "Email, password and CIN are required", "signup");
      }
      return {
        email: data.email.trim().toLowerCase(),
        password: data.password,
        cin: data.cin.trim(),
        phone: typeof data?.phone === "string" ? data.phone.trim() || undefined : undefined,
        region: typeof data?.region === "string" ? data.region.trim() || undefined : undefined,
      };
    },
  )
  .handler(async ({ data }): Promise<ClientSession> => {
    // The KYC record already exists in crm.customers (seeded via BSS import / legacy DB).
    // business-api links the new portal account to it after proofing the CIN.
    const result = await postCredential<SignupResponse>("/api/v1/auth/signup", {
      email: data.email,
      password: data.password,
      cin: data.cin,
      ...(data.phone ? { phone: data.phone } : {}),
      ...(data.region ? { region: data.region } : {}),
    });

    const session: ClientSession = {
      sub: result.email,
      role: "client",
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
    };

    await writeSessionCookie(session);
    return session;
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  const session = await readSession();
  if (session) {
    // Revoke server-side first so the token dies even if the browser keeps the cookie.
    try {
      await businessApi<{ signed_out: boolean }>("/api/v1/auth/logout", {
        method: "POST",
        body: {},
      });
    } catch {
      /* already expired or backend down — clearing the cookie is still correct */
    }
  }
  clearSessionCookie();
});
