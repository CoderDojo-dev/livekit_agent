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

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError || (error as ApiError)?.name === "ApiError";
}

/** 401 — the session is gone. The UI must send the user back to /login. */
export function isUnauthenticated(error: unknown): boolean {
  return isApiError(error) && error.status === 401;
}

/** 403 — authenticated but out-ranked. Matches require_role() in security.py. */
export function isForbidden(error: unknown): boolean {
  return isApiError(error) && error.status === 403;
}

/** 429 — portal_auth lockout (5 failures / 15 min) or the login/signup rate bucket. */
export function isRateLimited(error: unknown): boolean {
  return isApiError(error) && error.status === 429;
}

/** Human-readable copy for <ErrorState>. Never leaks a stack trace. */
export function errorMessage(error: unknown): string {
  if (isRateLimited(error))
    return "Too many attempts. For your safety, try again in about 15 minutes.";
  if (isForbidden(error)) return "Your account does not grant access to this page.";
  if (isUnauthenticated(error)) return "Your session has expired. Sign in again.";
  if (isApiError(error)) return error.detail || "The service returned an unexpected response.";
  if (typeof error === "string") return error;
  return "Could not reach the service. Check that business-api is running.";
}
