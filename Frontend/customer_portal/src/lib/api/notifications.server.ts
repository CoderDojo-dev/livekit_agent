import { createServerFn } from "@tanstack/react-start";
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
  .handler(() =>
    businessApi<{ items: NotificationItem[] }>("/api/v1/me/notifications?limit=20", {}),
  );
