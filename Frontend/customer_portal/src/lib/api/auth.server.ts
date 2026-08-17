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
  customer_id: string | null;
};

/**
 * The portal is a client-only surface. business-api will happily authenticate a
 * conseiller/superviseur/administrateur here, but "client" is absent from
 * _ROLE_RANK, so such a session can reach nothing except /auth/*: the shell
 * would render and then 403 on every read. Refuse at the door instead, and
 * never persist a token we are not going to use.
 */
function assertClient(
  payload: LoginResponse,
  path: string,
): asserts payload is LoginResponse & { kind: "client"; customer_id: string } {
  if (payload.kind !== "client" || !payload.customer_id) {
    throw new ApiError(
      403,
      "This portal is for customer accounts. Staff should use the advisor console.",
      path,
    );
  }
}

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

    assertClient(result, "/api/v1/auth/login");

    const session: ClientSession = {
      sub: result.email,
      role: "client",
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
      customerId: result.customer_id,
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
  customer_id: string | null;
};

export const signup = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string; cin: string; msisdn: string }) => {
    if (
      typeof data?.email !== "string" ||
      typeof data?.password !== "string" ||
      typeof data?.cin !== "string" ||
      typeof data?.msisdn !== "string"
    ) {
      throw new ApiError(400, "Email, password, CIN and phone number are required", "signup");
    }
    const cin = data.cin.replace(/\D/g, "");
    if (cin.length < 4) {
      throw new ApiError(400, "Enter at least the last four digits of your CIN", "signup");
    }
    return {
      email: data.email.trim().toLowerCase(),
      password: data.password,
      cin_last4: cin.slice(-4),
      msisdn: data.msisdn.replace(/\s/g, ""),
    };
  })
  .handler(async ({ data }): Promise<ClientSession> => {
    // The KYC record already exists in crm.customers. business-api links the new portal account
    // to it by matching the MSISDN on crm.subscriptions and proofing the last four CIN digits.
    const result = await postCredential<SignupResponse>("/api/v1/auth/signup", {
      email: data.email,
      password: data.password,
      cin_last4: data.cin_last4,
      msisdn: data.msisdn,
    });

    assertClient(result, "/api/v1/auth/signup");

    const session: ClientSession = {
      sub: result.email,
      role: "client",
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
      customerId: result.customer_id,
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
