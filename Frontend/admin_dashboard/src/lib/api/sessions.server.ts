import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

export type CallSessionRow = {
  session_id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  preferred_language: string | null;
  msisdn: string | null;
  channel: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
  disposition: string | null;
  max_frustration: number | null;
  recording_consent: boolean;
  has_recording: boolean;
  turn_count: number;
};

export type SessionIndex = {
  sessions: CallSessionRow[];
  total: number;
  limit: number;
  offset: number;
};

export type TranscriptTurnRow = {
  index: number;
  speaker: string;
  agent: string | null;
  text: string | null;
};

export type SentimentRow = {
  index: number;
  score: number;
  label: string;
};

export type SessionDetail = {
  session_id: string;
  disposition: string | null;
  duration_seconds: number | null;
  max_frustration: number | null;
  turns: TranscriptTurnRow[];
  sentiment: SentimentRow[];
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  disposition: z.string().trim().max(40).optional(),
  search: z.string().trim().max(40).optional(),
});

const DetailInput = z.object({
  sessionId: z.string().uuid(),
});

export const listSessions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<SessionIndex>("/api/v1/sessions", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.disposition ? { disposition: data.disposition } : {}),
        ...(data.search ? { search: data.search } : {}),
      },
      role: context.session.role,
    }),
  );

export const getSessionDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("conseiller")])
  .inputValidator((data: unknown) => DetailInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(data.sessionId)}`, {
      method: "GET",
      role: context.session.role,
    }),
  );
