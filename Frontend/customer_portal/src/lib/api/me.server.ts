import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

type Me = {
  subject: string;
  /** Principal.kind in infrastructure/auth/principal.py. "service" is the
   * X-API-Key machine principal; it can never reach the portal, but the type
   * must not lie about what the endpoint can return. */
  kind: "staff" | "client" | "service";
  role: string;
  account_id: string | null;
  customer_id: string | null;
};

/**
 * The controller endpoint-the only one used by the customer portal to confirm WHO the bearer
 * is. The backend reads the identity from the token, never from the request body or headers.
 */
export const fetchMe = createServerFn({ method: "GET" }).handler(async (): Promise<Me | null> => {
  try {
    return await businessApi<Me>("/api/v1/auth/me", {});
  } catch {
    return null;
  }
});

export type ProfileDetail = {
  customer_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  preferred_language: string;
  region: string | null;
  city: string | null;
  address_lines: string[];
  account_number: string | null;
  customer_since: string | null;
  vip: boolean;
  status: string;
  plan: string | null;
  msisdn: string | null;
};

export const fetchProfileDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<ProfileDetail> =>
    businessApi<ProfileDetail>("/api/v1/me/profile/detail", {}),
  );
