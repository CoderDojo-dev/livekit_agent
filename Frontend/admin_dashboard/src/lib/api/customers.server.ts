import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

/* ---------- wire types: exactly what SupervisionRepository.customer_list() serialises ---------- */

export type CustomerRow = {
  customer_id: string;
  name: string;
  email: string | null;
  contact_number: string | null;
  preferred_language: string;
  segment: string | null;
  vip: boolean;
  fraud_suspected: boolean;
  status: string;
  city: string | null;
};

export type CustomerPage = {
  customers: CustomerRow[];
  total: number;
  limit: number;
  offset: number;
};

export type CustomerSubscription = {
  subscription_id: string;
  msisdn: string;
  plan: string;
  status: string;
};

export type CustomerInvoice = {
  invoice: string;
  amount: number;
  status: string;
};

export type CustomerTicket = {
  glpi_id: number | string;
  status: string;
  subject: string;
};

export type Customer360 = {
  customer_id: string;
  name: string;
  vip: boolean;
  preferred_language: string;
  subscriptions: CustomerSubscription[];
  open_invoices: CustomerInvoice[];
  tickets: CustomerTicket[];
};

/* ---------- server functions ---------- */

export const listCustomers = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as {
      search?: unknown;
      status?: unknown;
      limit?: unknown;
      offset?: unknown;
    };
    const status = typeof input.status === "string" ? input.status : "";
    const limit = Number(input.limit);
    const offset = Number(input.offset);
    return {
      search: typeof input.search === "string" ? input.search.slice(0, 120) : "",
      status: ["", "active", "suspended", "closed"].includes(status) ? status : "",
      limit: Number.isInteger(limit) && limit >= 1 && limit <= 100 ? limit : 25,
      offset: Number.isInteger(offset) && offset >= 0 ? offset : 0,
    };
  })
  .handler(async ({ data, context }) =>
    businessApi<CustomerPage>("/api/v1/customers", {
      method: "GET",
      query: {
        search: data.search,
        status: data.status,
        limit: data.limit,
        offset: data.offset,
      },
      role: context.session.role,
    }),
  );

export const getCustomer360 = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { customerId?: unknown };
    if (typeof input.customerId !== "string") {
      throw new Error("customerId is required");
    }
    return { customerId: input.customerId };
  })
  .handler(async ({ data, context }) =>
    businessApi<Customer360>(`/api/v1/customers/${encodeURIComponent(data.customerId)}/360`, {
      method: "GET",
      role: context.session.role,
    }),
  );
