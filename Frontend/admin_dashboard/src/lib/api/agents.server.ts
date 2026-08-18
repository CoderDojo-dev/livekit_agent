import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

const NullableCounter = z.number().int().nonnegative().nullable();

const DailyPointSchema = z.object({
  day: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  attributed_calls: z.number().int().nonnegative(),
  attributed_call_duration_seconds: z.number().int().nonnegative(),
  provider_input_tokens: NullableCounter,
  provider_output_tokens: NullableCounter,
});

const PersonaSchema = z.object({
  persona: z.string().min(1),
  attributed_calls: z.number().int().nonnegative(),
  completed_calls: z.number().int().nonnegative(),
  attributed_call_duration_seconds: z.number().int().nonnegative(),
  average_completed_call_duration_seconds: z.number().nonnegative().nullable(),
  last_observed_at: z.string().datetime({ offset: true }).nullable(),
  provider_input_tokens: NullableCounter,
  provider_output_tokens: NullableCounter,
  token_event_count: z.number().int().nonnegative(),
  daily: z.array(DailyPointSchema),
});

export const AgentActivitySchema = z.object({
  window: z.object({
    days: z.number().int().min(1).max(365),
    timezone: z.literal("UTC"),
    from: z.string().datetime({ offset: true }),
    to: z.string().datetime({ offset: true }),
  }),
  definitions: z.object({
    agent_kind: z.literal("persona_class"),
    duration_kind: z.literal("non_exclusive_attributed_call_duration"),
    token_source: z.literal("provider_reported"),
    token_history: z.literal("forward_only_no_backfill"),
  }),
  totals: z.object({
    global_unique_calls: z.number().int().nonnegative(),
    persona_call_attributions: z.number().int().nonnegative(),
    attributed_call_duration_seconds: z.number().int().nonnegative(),
    provider_input_tokens: NullableCounter,
    provider_output_tokens: NullableCounter,
  }),
  personas: z.array(PersonaSchema),
});

export type AgentActivity = z.infer<typeof AgentActivitySchema>;
export type AgentActivityPersona = z.infer<typeof PersonaSchema>;
export type AgentDailyPoint = z.infer<typeof DailyPointSchema>;

const InputSchema = z.object({
  days: z.number().int().min(1).max(365).default(30),
});

export const AgentActivityInputSchema = InputSchema;

export const getAgentActivity = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((raw: unknown) => InputSchema.parse(raw ?? {}))
  .handler(async ({ data, context }) => {
    const response = await businessApi<unknown>("/api/v1/agents/activity", {
      method: "GET",
      query: { days: data.days },
      role: context.session.role,
    });
    return AgentActivitySchema.parse(response);
  });
