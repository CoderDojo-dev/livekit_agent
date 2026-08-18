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
  status: string;
  plan: string | null;
  msisdn: string | null;
};

export const fetchProfileDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<ProfileDetail> =>
    businessApi<ProfileDetail>("/api/v1/me/profile/detail", {}),
  );

export type Subscription360 = {
  subscription_id: string;
  msisdn: string | null;
  plan: string | null;
  status: string | null;
};

export type Customer360 = {
  customer_id: string;
  name: string;
  preferred_language: string;
  subscriptions: Subscription360[];
  open_invoices: {
    invoice: string;
    amount: number;
    outstanding: number;
    status: string;
  }[];
  tickets: { glpi_id: string | null; status: string; subject: string | null }[];
};

/** GET /api/v1/me/profile — the signed-in customer's own 360 (customer_360). */
export const fetchProfile360 = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<Customer360> => businessApi<Customer360>("/api/v1/me/profile", {}));
