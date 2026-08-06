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
  /** Invoice face value (`total_amount`). */
  amount: number;
  /** FEATURE_21 — added to the repository dict (additive). Balance still owed. */
  outstanding: number;
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

export type CustomerPayment = {
  payment_id: string;
  amount: number;
  currency_code: string;
  method: string;
  status: string;
  gateway_reference: string | null;
  invoice: string | null;
  paid_at: string | null;
  created_at: string | null;
};

export type CustomerPaymentPlan = {
  plan_id: string;
  total_amount: number;
  installment_count: number;
  installment_amount: number;
  deferral_until: string | null;
  status: string;
  policy_verdict_id: string | null;
  created_at: string | null;
};

export type CustomerConsent = {
  consent_id: string;
  consent_type: string;
  granted: boolean;
  language: string | null;
  session_id: string;
  captured_at: string | null;
};

export type CustomerLedger = {
  customer_id: string;
  payments: CustomerPayment[];
  payment_plans: CustomerPaymentPlan[];
  consents: CustomerConsent[];
};

export type CustomerBalance = {
  balance_id: string;
  subscription_id: string;
  msisdn: string | null;
  balance_type: string;
  balance_value: number;
  balance_unit: string;
  status: string;
  expiry_date: string | null;
  updated_at: string | null;
};

export type CustomerPlanChange = {
  change_id: string;
  subscription_id: string | null;
  msisdn: string | null;
  from_plan: string | null;
  to_plan: string;
  changed_by: string;
  effective_date: string | null;
  created_at: string | null;
};

type ServiceEventBase = {
  event_id: string;
  status: string;
  occurred_at: string | null;
  subscription_id: string | null;
  msisdn: string | null;
  reference: string | null;
};

export type RechargeEvent = ServiceEventBase & {
  source: "recharge";
  amount: number;
  bonus_amount: number;
  channel: string;
};

export type SimCaseEvent = ServiceEventBase & {
  source: "sim_case";
  action: string;
};

export type SimOrderEvent = ServiceEventBase & {
  source: "sim_order";
  sim_type: string;
};

export type ProvisioningEvent = ServiceEventBase & {
  source: "provisioning";
  action_type: string;
  completed_at: string | null;
};

/** Discriminated on `source` — the repository normalises four tables into one ordered list. */
export type ServiceEvent = RechargeEvent | SimCaseEvent | SimOrderEvent | ProvisioningEvent;

export type CustomerServiceActions = {
  customer_id: string;
  balances: CustomerBalance[];
  plan_changes: CustomerPlanChange[];
  events: ServiceEvent[];
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

export const getCustomerLedger = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { customerId?: unknown };
    if (typeof input.customerId !== "string") {
      throw new Error("customerId is required");
    }
    return { customerId: input.customerId };
  })
  .handler(async ({ data, context }) =>
    businessApi<CustomerLedger>(`/api/v1/customers/${encodeURIComponent(data.customerId)}/ledger`, {
      method: "GET",
      role: context.session.role,
    }),
  );

export const getCustomerServiceActions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { customerId?: unknown };
    if (typeof input.customerId !== "string") {
      throw new Error("customerId is required");
    }
    return { customerId: input.customerId };
  })
  .handler(async ({ data, context }) =>
    businessApi<CustomerServiceActions>(
      `/api/v1/customers/${encodeURIComponent(data.customerId)}/service-actions`,
      {
        method: "GET",
        role: context.session.role,
      },
    ),
  );
