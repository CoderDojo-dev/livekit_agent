import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type TicketRow = {
  ticket_id: string;
  status: string;
  subject: string | null;
  category: string;
  priority: string | null;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  subscription_id: string | null;
  created_at: string | null;
  last_synced_at: string | null;
};

export type TicketIndex = {
  tickets: TicketRow[];
  total: number;
  counts: Record<string, number>;
  limit: number;
  offset: number;
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  status: z.string().trim().max(20).optional(),
  category: z.string().trim().max(40).optional(),
  priority: z.string().trim().max(10).optional(),
  search: z.string().trim().max(80).optional(),
});

export const listTickets = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<TicketIndex>("/api/v1/tickets", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.status ? { status: data.status } : {}),
        ...(data.category ? { category: data.category } : {}),
        ...(data.priority ? { priority: data.priority } : {}),
        ...(data.search ? { search: data.search } : {}),
      },
      role: context.session.role,
    }),
  );
