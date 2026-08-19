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

/** 429 — portal_auth lockout (5 failures / 15 min) or the login/signup rate bucket. */
export function isRateLimited(error: unknown): boolean {
  return toApiError(error)?.status === 429;
}

const RATE_LIMIT_COPY = "Too many attempts. For your safety, try again in about 15 minutes.";
const UNREACHABLE_COPY = "Could not reach the service. Check that business-api is running.";

/** Credential surfaces, where 401/403 mean the attempt was refused, not that a session died. */
const LOGIN_PATHS = new Set(["login", "/api/v1/auth/login"]);
const SIGNUP_PATHS = new Set(["signup", "/api/v1/auth/signup"]);

/** Password change, where 401 means the current password was wrong. */
const PASSWORD_PATHS = new Set(["password", "/api/v1/auth/password"]);

/** Human-readable copy for the sign-in form. Never leaks a stack trace. */
function loginMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 400:
      return apiError.detail || "Email and password are required.";
    case 401:
      return "Incorrect email or password.";
    case 403:
      return apiError.detail || "This account cannot access the portal.";
    case 429:
      return RATE_LIMIT_COPY;
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return UNREACHABLE_COPY;
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "Sign-in failed. Try again.";
  }
}

/** Human-readable copy for the sign-up form. Never leaks a stack trace. */
function signupMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 400:
      return apiError.detail || "Check the information you entered.";
    case 401:
      return apiError.detail || "We could not match those details to an account.";
    case 403:
      return apiError.detail || "This account cannot access the portal.";
    case 429:
      return RATE_LIMIT_COPY;
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return UNREACHABLE_COPY;
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "Sign-up failed. Try again.";
  }
}

/** Human-readable copy for the password change panel. Never leaks a stack trace. */
function passwordMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 400:
      return apiError.detail || "Choose a different password.";
    case 401:
      return apiError.detail || "Incorrect password.";
    case 429:
      return RATE_LIMIT_COPY;
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return UNREACHABLE_COPY;
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "Password change failed. Try again.";
  }
}

/** Human-readable copy for every other surface. Never leaks a stack trace. */
function generalMessage(apiError: ApiError): string {
  switch (apiError.status) {
    case 401:
      return "Your session has expired. Sign in again.";
    case 403:
      return "Your account does not grant access to this page.";
    case 429:
      return RATE_LIMIT_COPY;
    case 502:
      return "The service returned an invalid response. Try again.";
    case 503:
      return UNREACHABLE_COPY;
    case 504:
      return "The service did not respond in time. Try again.";
    default:
      return apiError.detail || "The service returned an unexpected response.";
  }
}

/** Human-readable copy for forms, toasts and <ErrorState>. Never leaks a stack trace. */
export function errorMessage(error: unknown): string {
  const apiError = toApiError(error);

  if (apiError) {
    if (LOGIN_PATHS.has(apiError.path)) return loginMessage(apiError);
    if (SIGNUP_PATHS.has(apiError.path)) return signupMessage(apiError);
    if (PASSWORD_PATHS.has(apiError.path)) return passwordMessage(apiError);
    return generalMessage(apiError);
  }

  if (typeof error === "string") return error;
  return UNREACHABLE_COPY;
}
