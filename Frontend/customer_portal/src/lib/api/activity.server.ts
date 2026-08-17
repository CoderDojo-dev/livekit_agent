import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

export type Paged<T> = { total: number; limit: number; offset: number; items: T[] };

export type ConversationSummary = {
  session_id: string;
  channel: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  disposition: string | null;
  turns: number;
};

export type ConversationTurn = {
  index: number;
  speaker: "caller" | "agent";
  agent: string | null;
  language: string | null;
  text: string | null;
  at: string | null;
};

export type ConversationDetail = Omit<ConversationSummary, "turns"> & {
  turns: ConversationTurn[];
};

export const fetchConversations = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(10),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<Paged<ConversationSummary>>(
      `/api/v1/me/conversations?limit=${data.limit}&offset=${data.offset}`,
      {},
    ),
  );

export const fetchConversation = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(z.object({ sessionId: z.string().uuid() }))
  .handler(({ data }) =>
    businessApi<ConversationDetail>(
      `/api/v1/me/conversations/${encodeURIComponent(data.sessionId)}`,
      {},
    ),
  );

export type CallbackItem = {
  scheduled_time: string | null;
  preferred_window: string | null;
  status: "pending" | "completed" | "cancelled";
  reason: string | null;
  completed_at: string | null;
};

export const fetchCallbacks = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<{ items: CallbackItem[] }>("/api/v1/me/callbacks?limit=20", {}));
