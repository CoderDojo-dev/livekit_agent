import { createServerFn } from "@tanstack/react-start";
import { serverConfig } from "./config";
import { ApiError, toApiError } from "./errors";
import { clearSessionCookie, readSession, writeSessionCookie } from "./session.server";
import { ROLE_RANK, type AdminSession, type BackendRole } from "./session";

type LoginResponse = {
  token: string;
  expires_at: string;
  email: string;
  role: string;
  kind: string;
  customer_id: string | null;
};

type MeResponse = {
  subject: string;
  kind: string;
  role: string;
  customer_id: string | null;
};

export type RevokeAllSessionsResult = { sessions_revoked: number };

/**
 * Safe browser-visible session projection.
 * The opaque backend token must never leave server-side code.
 */
export type SessionView = Pick<AdminSession, "sub" | "role" | "exp">;

type HttpMethod = "GET" | "POST";

class MalformedUpstreamResponse extends ApiError {
  constructor(path: string, detail = "business-api returned a malformed JSON body") {
    super(502, detail, path);
    this.name = "MalformedUpstreamResponse";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isBackendRole(value: unknown): value is BackendRole {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(ROLE_RANK, value);
}

function parseLoginResponse(value: unknown): LoginResponse | null {
  if (!isRecord(value)) return null;

  if (
    typeof value["token"] !== "string" ||
    value["token"].length === 0 ||
    typeof value["expires_at"] !== "string" ||
    typeof value["email"] !== "string" ||
    value["email"].length === 0 ||
    typeof value["role"] !== "string" ||
    typeof value["kind"] !== "string" ||
    !isNullableString(value["customer_id"])
  ) {
    return null;
  }

  return {
    token: value["token"],
    expires_at: value["expires_at"],
    email: value["email"],
    role: value["role"],
    kind: value["kind"],
    customer_id: value["customer_id"],
  };
}

function parseMeResponse(value: unknown): MeResponse | null {
  if (!isRecord(value)) return null;

  if (
    typeof value["subject"] !== "string" ||
    value["subject"].length === 0 ||
    typeof value["kind"] !== "string" ||
    typeof value["role"] !== "string" ||
    !isNullableString(value["customer_id"])
  ) {
    return null;
  }

  return {
    subject: value["subject"],
    kind: value["kind"],
    role: value["role"],
    customer_id: value["customer_id"],
  };
}

function sessionView(session: AdminSession): SessionView {
  return {
    sub: session.sub,
    role: session.role,
    exp: session.exp,
  };
}

async function requestJson<T>(
  method: HttpMethod,
  path: string,
  body?: unknown,
  token?: string,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;

  try {
    response = await fetch(`${serverConfig.businessApiUrl()}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
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

      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      } else if (parsed.detail !== undefined) {
        detail = JSON.stringify(parsed.detail);
      }
    } catch {
      // Preserve the raw non-JSON response.
    }

    throw new ApiError(response.status, detail, path);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new MalformedUpstreamResponse(path);
  }
}

/**
 * Attempts backend revocation, but always removes the local cookie.
 */
async function revokeAndClear(token?: string): Promise<void> {
  try {
    if (token) {
      await requestJson<{ signed_out: boolean }>("POST", "/api/v1/auth/logout", {}, token);
    }
  } catch {
    // Revocation may already be effective or the backend may be unavailable.
  } finally {
    clearSessionCookie();
  }
}

async function validatedSession(): Promise<AdminSession | null> {
  const session = await readSession();

  if (!session) {
    // Also removes expired, malformed, or unverifiable cookie data.
    clearSessionCookie();
    return null;
  }

  let rawMe: unknown;

  try {
    rawMe = await requestJson<unknown>("GET", "/api/v1/auth/me", undefined, session.token);
  } catch (error) {
    if (error instanceof MalformedUpstreamResponse) {
      await revokeAndClear(session.token);
      return null;
    }

    if (toApiError(error)?.status === 401 || toApiError(error)?.status === 403) {
      clearSessionCookie();
      return null;
    }

    /*
     * A network failure, timeout, or backend 5xx is not proof that the
     * session is invalid. Keep the cookie and let the root error boundary
     * provide retry behavior.
     */
    throw error;
  }

  const me = parseMeResponse(rawMe);

  if (
    !me ||
    me.kind !== "staff" ||
    !isBackendRole(me.role) ||
    me.subject !== session.sub ||
    me.role !== session.role
  ) {
    await revokeAndClear(session.token);
    return null;
  }

  return session;
}

export const getSession = createServerFn({ method: "GET" }).handler(
  async (): Promise<SessionView | null> => {
    const session = await validatedSession();
    return session ? sessionView(session) : null;
  },
);

export const login = createServerFn({ method: "POST" })
  .inputValidator((data: { email: string; password: string }) => {
    if (typeof data?.email !== "string" || typeof data?.password !== "string") {
      throw new ApiError(400, "Email and password are required", "login");
    }

    return {
      email: data.email.trim().toLowerCase(),
      password: data.password,
    };
  })
  .handler(async ({ data }): Promise<SessionView> => {
    const rawResult = await requestJson<unknown>("POST", "/api/v1/auth/login", {
      email: data.email,
      password: data.password,
    });

    const result = parseLoginResponse(rawResult);

    if (!result) {
      const token =
        isRecord(rawResult) && typeof rawResult["token"] === "string"
          ? rawResult["token"]
          : undefined;

      await revokeAndClear(token);

      throw new MalformedUpstreamResponse(
        "/api/v1/auth/login",
        "business-api returned an invalid login response",
      );
    }

    /*
     * The backend session has already been committed at this point.
     * Revoke it before refusing a non-staff or unsupported account.
     */
    if (result.kind !== "staff" || !isBackendRole(result.role)) {
      await revokeAndClear(result.token);

      throw new ApiError(403, "This account cannot access the admin console", "login");
    }

    const expiresAtMs = new Date(result.expires_at).getTime();

    if (!Number.isFinite(expiresAtMs) || expiresAtMs <= Date.now()) {
      await revokeAndClear(result.token);

      throw new MalformedUpstreamResponse(
        "/api/v1/auth/login",
        "business-api returned an invalid session expiry",
      );
    }

    const session: AdminSession = {
      sub: result.email,
      role: result.role,
      exp: Math.floor(expiresAtMs / 1000),
      token: result.token,
    };

    await writeSessionCookie(session);

    return sessionView(session);
  });

export const logout = createServerFn({ method: "POST" }).handler(async (): Promise<void> => {
  const session = await readSession();

  if (session) {
    try {
      await requestJson<{ signed_out: boolean }>("POST", "/api/v1/auth/logout", {}, session.token);
    } catch {
      /*
       * The token may already be expired or the backend may be down.
       * Local logout must still succeed.
       */
    }
  }

  clearSessionCookie();
});

export const revokeAllSessions = createServerFn({ method: "POST" }).handler(
  async (): Promise<RevokeAllSessionsResult> => {
    const session = await readSession();

    if (!session) {
      throw new ApiError(401, "Not authenticated", "sessions");
    }

    const result = await requestJson<unknown>(
      "POST",
      "/api/v1/auth/sessions/revoke-all",
      {},
      session.token,
    );

    if (!isRecord(result) || typeof result["sessions_revoked"] !== "number") {
      throw new ApiError(502, "business-api returned an invalid revoke-all response", "sessions");
    }

    clearSessionCookie();
    return { sessions_revoked: result["sessions_revoked"] };
  },
);

export const changePassword = createServerFn({ method: "POST" })
  .inputValidator((data: { currentPassword: string; newPassword: string }) => {
    if (typeof data?.currentPassword !== "string" || typeof data?.newPassword !== "string") {
      throw new ApiError(400, "Both passwords are required", "password");
    }

    return {
      currentPassword: data.currentPassword,
      newPassword: data.newPassword,
    };
  })
  .handler(async ({ data }): Promise<void> => {
    const session = await readSession();

    if (!session) {
      throw new ApiError(401, "Not authenticated", "password");
    }

    await requestJson<{ changed: boolean }>(
      "POST",
      "/api/v1/auth/password",
      {
        current_password: data.currentPassword,
        new_password: data.newPassword,
      },
      session.token,
    );

    /*
     * Password changes revoke all sessions, including the current one.
     */
    clearSessionCookie();
  });
