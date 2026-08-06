import { formatBusinessTime } from "@/lib/nexus/callback-view";

/** D18.2 — billing.notifications.status is CHECK-constrained to queued/sent/failed, but only two
 *  are ever written: _persist passes "sent" or "failed", and the column default is 'sent'. There is
 *  no `sent` key in status.ts, so it maps onto `resolved` - the same mapping decision-view.ts's
 *  actionStatusKey already uses for `succeeded`. The default arm exists so an out-of-band value can
 *  never render a blank chip (the defect Features 1, 3 and 4 each hit). */
export function notificationStatusKey(status: string | null): string {
  switch (status) {
    case "sent":
      return "resolved";
    case "failed":
      return "failed";
    case "queued":
      return "queued";
    default:
      return "open";
  }
}

const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
};

export function channelLabel(channel: string | null): string {
  if (!channel) return "\u2014";
  return CHANNEL_LABELS[channel] ?? channel;
}

/** D18.3 — the five codes in notification_service/templates.py. template_code is a nullable
 *  String(80) with no CheckConstraint, so an unmapped code renders raw rather than being hidden. */
const TEMPLATE_LABELS: Record<string, string> = {
  advisor_callback: "Advisor callback",
  callback_scheduled: "Callback scheduled",
  ticket_created: "Ticket created",
  ticket_resolved: "Ticket resolved",
  ticket_updated: "Ticket updated",
};

export function templateLabel(template: string | null): string {
  if (!template) return "\u2014";
  return TEMPLATE_LABELS[template] ?? template;
}

/** D18.1 — customer_id is NULL for advisor-addressed sends (notify_advisor posts an empty
 *  customer_id, which to_uuid() turns into NULL) and for any non-UUID caller id. "Unattributed"
 *  is the honest word: the row is real, the recipient simply is not a row in crm.customers.
 *  A NULL customer and a customer we failed to join are different facts, so they read differently. */
export function notificationRecipient(name: string | null, customerId: string | null): string {
  const trimmed = name?.trim();
  if (trimmed) return trimmed;
  return customerId ? "Unknown customer" : "Unattributed";
}

export const STATUS_ORDER = ["sent", "failed", "queued"] as const;

export const STATUS_LABELS: Record<string, string> = {
  sent: "Sent",
  failed: "Failed",
  queued: "Queued",
};

/** Mirrors ticket-view.statusCount — counts omit zero-row statuses; never render a blank. */
export function statusCount(counts: Record<string, number> | undefined, status: string): number {
  return counts?.[status] ?? 0;
}

/** D18.5 — sourced from created_at, never sent_at. _persist does not set sent_at; the column's
 *  server_default fills it at INSERT even for failed rows, so it records when the attempt was
 *  logged, not when a message was delivered. Same reasoning as ticket-view's "Synced" column. */
export function notificationTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone ?? "UTC");
}
