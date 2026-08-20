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
  /** Administrator note (migration 0020). Null until an admin writes one. The agent reads the
   *  same field through the ticket mirror, so what is shown here is what the caller will hear. */
  admin_note: string | null;
  note_author: string | null;
  note_updated_at: string | null;
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

/* ---------------------------------------------------------------------------------------------
 * Manual ticket update
 *
 * business-api applies this through ticketing-glpi, which writes GLPI FIRST and only then the
 * local mirror — so the two can never disagree. If GLPI refuses or is unreachable the whole call
 * fails and nothing is written locally; the dialog reports that rather than showing a status the
 * upstream never took.
 *
 * The note lands in ticketing.tickets.admin_note, which is exactly what the agent's
 * get_ticket_status / lookup_tickets tools return — so an advisor's note reaches the caller on
 * their next call with no agent-side change. Sending "" clears an existing note.
 * ------------------------------------------------------------------------------------------- */

export const TICKET_ADMIN_STATUSES = [
  "open",
  "in_progress",
  "pending",
  "resolved",
  "closed",
] as const;

const AdminUpdateInput = z
  .object({
    ticketId: z.string().min(1).max(40),
    status: z.enum(TICKET_ADMIN_STATUSES).optional(),
    note: z.string().max(2000).optional(),
  })
  // Mirrors the backend's own precondition, so an empty submit fails at the edge with a clear
  // message instead of making a doomed round trip.
  .refine((value) => value.status !== undefined || value.note !== undefined, {
    message: "Provide a status, a note, or both.",
  });

export const adminUpdateTicket = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => AdminUpdateInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<TicketRow & { admin_note?: string | null }>(
      `/api/v1/tickets/${encodeURIComponent(data.ticketId)}`,
      {
        method: "PATCH",
        body: {
          ...(data.status === undefined ? {} : { status: data.status }),
          ...(data.note === undefined ? {} : { note: data.note }),
        },
        role: context.session.role,
      },
    ),
  );
