import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";
import type { Paged } from "./activity.server";

export type BillingAccount = {
  account_number: string;
  account_type: "postpaid" | "hybrid";
  billing_cycle_day: number | null;
  currency_code: string;
  status: string;
};

export type InvoiceItem = {
  invoice_number: string;
  account_number: string | null;
  period_start: string | null;
  period_end: string | null;
  issue_date: string | null;
  due_date: string | null;
  subtotal: number | null;
  tax_amount: number | null;
  total_amount: number | null;
  outstanding_amount: number | null;
  currency_code: string;
  status: "draft" | "issued" | "paid" | "partial" | "overdue" | "disputed" | "void";
};

export type PaymentItem = {
  amount: number | null;
  currency_code: string;
  method: string | null;
  status: string;
  paid_at: string | null;
  invoice_number: string | null;
};

export type BillingPayload = {
  accounts: BillingAccount[];
  total_outstanding: number;
  currency_code: string;
  /** Paged: the account figures above are whole-account and do not follow it. */
  invoices: Paged<InvoiceItem>;
  payments: PaymentItem[];
};

export type BalanceItem = {
  msisdn: string | null;
  balance_type: "main" | "data" | "voice" | "sms";
  value: number | null;
  unit: "TND" | "GB" | "MB" | "MIN" | "SMS";
  expires_on: string | null;
  status: "active" | "expired" | "suspended";
};

export type RechargeItem = {
  msisdn: string | null;
  amount: number | null;
  bonus_amount: number | null;
  channel: "app" | "web" | "ussd" | "scratch_card" | "agent";
  status: "pending" | "completed" | "failed";
  created_at: string | null;
};

export type BalancePayload = { balances: BalanceItem[]; recharges: RechargeItem[] };

export const fetchBilling = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<BillingPayload>(`/api/v1/me/billing?limit=${data.limit}&offset=${data.offset}`, {}),
  );

export const fetchBalance = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<BalancePayload>("/api/v1/me/balance", {}));
