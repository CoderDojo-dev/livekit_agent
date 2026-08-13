import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type NotificationRow = {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  channel: string;
  template_code: string | null;
  status: string;
  failure_reason: string | null;
  sent_at: string | null;
  created_at: string | null;
};

export type NotificationIndex = {
  notifications: NotificationRow[];
  total: number;
  counts: Record<string, number>;
  limit: number;
  offset: number;
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  channel: z.string().trim().max(20).optional(),
  status: z.string().trim().max(20).optional(),
});

export const listNotifications = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<NotificationIndex>("/api/v1/notifications", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.channel ? { channel: data.channel } : {}),
        ...(data.status ? { status: data.status } : {}),
      },
      role: context.session.role,
    }),
  );
