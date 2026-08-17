import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";
import type { Paged } from "./activity.server";

/** ticketing.tickets CHECK constraint — five values, not four. */
export const TICKET_STATUSES = ["open", "in_progress", "pending", "resolved", "closed"] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

export type RequestItem = {
  reference: string;
  category: "network_complaint" | "formal_complaint" | "technical" | "billing" | "other";
  subject: string | null;
  status: TicketStatus;
  priority: "low" | "medium" | "high" | "urgent" | null;
  created_at: string | null;
  updated_at: string | null;
};

export const fetchRequests = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      status: z.enum(TICKET_STATUSES).optional(),
      limit: z.number().int().min(1).max(50).default(10),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) => {
    const params = new URLSearchParams({
      limit: String(data.limit),
      offset: String(data.offset),
    });
    if (data.status) params.set("status", data.status);
    return businessApi<Paged<RequestItem>>(`/api/v1/me/requests?${params.toString()}`, {});
  });
