import { serverConfig } from "./config";
import { ApiError } from "./errors";
import type { BackendRole } from "./session";

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** Query string params. undefined/null entries are dropped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  /** Injected as X-Role. Resolved from the session by authedMiddleware — never from the client. */
  role: BackendRole;
};

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${serverConfig.businessApiUrl()}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Server-only HTTP client for business-api.
 *
 * SECURITY: the sole place X-Role is ever set. The browser cannot influence it,
 * because `role` comes from the signed session cookie via authedMiddleware.
 */
export async function businessApi<T>(path: string, options: RequestOptions): Promise<T> {
  const { method = "GET", query, body, role } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), serverConfig.requestTimeoutMs());

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        "X-Role": role,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      signal: controller.signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (cause) {
    const offline = (cause as Error)?.name === "AbortError";
    throw new ApiError(
      offline ? 504 : 503,
      offline ? "business-api did not respond in time" : "business-api is unreachable",
      path,
    );
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) return undefined as T;

  const raw = await response.text();

  if (!response.ok) {
    // FastAPI shape: {"detail": "..."}
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail !== undefined) detail = JSON.stringify(parsed.detail);
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

/** Connectivity probe for the login screen and Settings. Never throws. */
export async function businessApiHealth(): Promise<{ reachable: boolean; detail?: string }> {
  try {
    await businessApi<{ status: string }>("/health", { role: "conseiller" });
    return { reachable: true };
  } catch (error) {
    return { reachable: false, detail: (error as ApiError)?.detail ?? "unknown error" };
  }
}
