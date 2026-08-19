import { describe, expect, it } from "vitest";
import { ApiError, errorMessage, isApiError, isForbidden, isRateLimited, isUnauthenticated, toApiError } from "./errors";

/** The shape TanStack Start's RPC delivers: a plain Error whose message only survives. */
function serialized(apiError: ApiError): Error {
  return new Error(apiError.message);
}

const STAFF_REFUSED = new ApiError(
  403,
  "This portal is for customer accounts. Staff should use the advisor console.",
  "/api/v1/auth/login",
);

describe("toApiError", () => {
  it("passes real ApiError instances through", () => {
    expect(toApiError(STAFF_REFUSED)).toBe(STAFF_REFUSED);
  });
  it("reconstructs ApiErrors from the serialized message", () => {
    const decoded = toApiError(serialized(STAFF_REFUSED));
    expect(decoded?.status).toBe(403);
    expect(decoded?.path).toBe("/api/v1/auth/login");
    expect(decoded?.detail).toBe(STAFF_REFUSED.detail);
  });
  it("returns null for anything else", () => {
    expect(toApiError(new Error("boom"))).toBeNull();
    expect(toApiError("boom")).toBeNull();
    expect(toApiError(undefined)).toBeNull();
    expect(toApiError(null)).toBeNull();
  });
});

describe("predicates", () => {
  it("recognize serialized errors", () => {
    expect(isApiError(serialized(STAFF_REFUSED))).toBe(true);
    expect(isForbidden(serialized(STAFF_REFUSED))).toBe(true);
    expect(isUnauthenticated(serialized(new ApiError(401, "nope", "/api/v1/me")))).toBe(true);
    expect(isRateLimited(serialized(new ApiError(429, "slow down", "/api/v1/auth/login")))).toBe(true);
  });
  it("stay false for unrelated errors", () => {
    expect(isApiError(new Error("boom"))).toBe(false);
    expect(isForbidden(new Error("boom"))).toBe(false);
  });
});

describe("errorMessage", () => {
  it("shows the backend detail for a staff login on the portal (regression: used to show a connectivity error)", () => {
    const message = errorMessage(serialized(STAFF_REFUSED));
    expect(message).toBe(STAFF_REFUSED.detail);
    expect(message).not.toContain("Could not reach the service");
  });

  it("treats a login 401 as bad credentials, not an expired session", () => {
    const message = errorMessage(serialized(new ApiError(401, "Incorrect email or password", "/api/v1/auth/login")));
    expect(message).toBe("Incorrect email or password.");
  });

  it("maps a login 429 to the lockout copy", () => {
    expect(errorMessage(serialized(new ApiError(429, "Too many attempts. Try again later.", "/api/v1/auth/login")))).toBe(
      "Too many attempts. For your safety, try again in about 15 minutes.",
    );
  });

  it("maps a login 503 to the connectivity copy", () => {
    expect(errorMessage(serialized(new ApiError(503, "business-api is unreachable", "/api/v1/auth/login")))).toBe(
      "Could not reach the service. Check that business-api is running.",
    );
  });

  it("surfaces signup failures verbatim", () => {
    expect(errorMessage(serialized(new ApiError(401, "We could not match those details to an account.", "/api/v1/auth/signup")))).toBe(
      "We could not match those details to an account.",
    );
  });

  it("treats a password-change 401 as a wrong current password", () => {
    expect(errorMessage(serialized(new ApiError(401, "Incorrect password", "/api/v1/auth/password")))).toBe(
      "Incorrect password",
    );
  });

  it("keeps session-expired copy for data surfaces", () => {
    expect(errorMessage(serialized(new ApiError(401, "Not authenticated", "session")))).toBe(
      "Your session has expired. Sign in again.",
    );
  });

  it("keeps the generic 403 copy for data surfaces", () => {
    expect(errorMessage(serialized(new ApiError(403, "forbidden", "/api/v1/me/invoices")))).toBe(
      "Your account does not grant access to this page.",
    );
  });

  it("falls back to the connectivity copy for unknown errors", () => {
    expect(errorMessage(new Error("boom"))).toBe("Could not reach the service. Check that business-api is running.");
  });

  it("passes local validation strings through", () => {
    expect(errorMessage("Name is required.")).toBe("Name is required.");
  });
});