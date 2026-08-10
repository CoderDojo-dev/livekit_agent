import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "./business-api";

type Me = {
  subject: string;
  kind: "staff" | "customer";
  role: string;
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
