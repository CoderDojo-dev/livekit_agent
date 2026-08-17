import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import type { Paged } from "./activity.server";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

export type NotificationItem = {
  channel: "sms" | "whatsapp" | "email";
  template_code: string | null;
  status: "queued" | "sent" | "failed";
  sent_at: string | null;
  created_at: string | null;
};

export const fetchNotifications = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(20),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<Paged<NotificationItem>>(
      `/api/v1/me/notifications?limit=${data.limit}&offset=${data.offset}`,
      {},
    ),
  );
