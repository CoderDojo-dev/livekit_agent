/** Typed transport errors. Thrown server-side, serialised to the client by TanStack Start. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly path: string;

  constructor(status: number, detail: string, path: string) {
    super(`business-api ${status} on ${path}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.path = path;
  }
}

/**
 * Matches the message format produced by the ApiError constructor. TanStack
 * Start's RPC serialization only preserves `message` on thrown errors, so a
 * server-side ApiError reaches the browser as a plain Error whose message
 * still encodes status, path and detail. Paths never contain ": ", so the
 * first occurrence is the real delimiter.
 */
const SERIALIZED_API_ERROR = /^business-api (\d{3}) on (.+?): ([\s\S]*)$/;

/** Reconstructs an ApiError from a real instance or a serialized plain Error. */
export function toApiError(error: unknown): ApiError | null {
  if (error instanceof ApiError) return error;
  if ((error as ApiError)?.name === "ApiError") return error as ApiError;

  const message = (error as { message?: unknown } | null)?.message;

  if (typeof message !== "string") return null;

  const match = message.match(SERIALIZED_API_ERROR);

  if (!match) return null;

  return new ApiError(Number(match[1]!), match[3]!, match[2]!);
}

export function isApiError(error: unknown): boolean {
  return toApiError(error) !== null;
}

/** 401 — the session is gone. The UI must send the user back to /login. */
export function isUnauthenticated(error: unknown): boolean {
  return toApiError(error)?.status === 401;
}

/** 403 — authenticated but out-ranked. Matches require_role() in security.py. */
export function isForbidden(error: unknown): boolean {
  return toApiError(error)?.status === 403;
}

/** Sign-in endpoint paths, where 401 means wrong credentials, not an expired session. */
const LOGIN_PATHS = new Set(["login", "/api/v1/auth/login"]);

/** Human-readable copy for the sign-in page. Never leaks a stack trace. */
function loginMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 400:
      return "Email and password are required.";
    case 401:
      return "Incorrect email or password.";
    case 403:
      return "This account cannot access the admin console.";
    case 429:
      return "Too many failed attempts. Try again in a few minutes.";
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return "Could not reach the service. Check that business-api is running.";
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "Sign-in failed. Try again.";
  }
}

/** Human-readable copy for every other page. Never leaks a stack trace. */
function generalMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 401:
      return "Your session has expired. Sign in again.";
    case 403:
      return "Your role does not grant access to this data.";
    case 404:
      return "The record was not found.";
    case 429:
      return "Too many attempts. Try again later.";
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return "Could not reach the service. Check that business-api is running.";
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "The service returned an unexpected response.";
  }
}

/** Human-readable copy for <ErrorState> and the sign-in form. */
export function errorMessage(error: unknown): string {
  const apiError = toApiError(error);

  if (apiError) {
    return LOGIN_PATHS.has(apiError.path) ? loginMessage(apiError) : generalMessage(apiError);
  }

  if (typeof error === "string") return error;
  return "Could not reach the service. Check that business-api is running.";
}
