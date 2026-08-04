import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- wire types: exactly what availability.py serialises ---------- */

export type CoverageHour = {
  at: string;
  local: string;
  advisors: number;
  languages: string[];
};

export type CoverageReport = {
  hours: CoverageHour[];
  uncovered_hours: string[];
  uncovered_by_language: Record<string, string[]>;
  languages: string[];
  advisors_total: number;
  timezone: string;
};

export type Shift = {
  id: string;
  advisor_id: string;
  weekday: number;
  weekday_name: string;
  start: string;
  end: string;
  is_active: boolean;
};

export type TimeOff = {
  id: string;
  advisor_id: string;
  starts_at: string;
  ends_at: string;
  reason: string | null;
};

export type AdvisorWeek = {
  advisor_id: string;
  shifts: Shift[];
  time_off: TimeOff[];
  timezone: string;
};

/* ---------- schemas ---------- */

const CoverageInput = z.object({
  days: z.number().int().min(1).max(30),
});

const AdvisorIdInput = z.object({
  advisorId: z.string().min(1),
});

const WindowSchema = z.object({
  weekday: z.number().int().min(0).max(6),
  start: z.string().regex(/^\d{2}:\d{2}$/),
  end: z.string().regex(/^\d{2}:\d{2}$/),
  is_active: z.boolean(),
});

const ReplaceScheduleInput = z.object({
  advisorId: z.string().min(1),
  windows: z.array(WindowSchema),
});

const CreateTimeOffInput = z.object({
  advisorId: z.string().min(1),
  starts_at: z.string().min(1),
  ends_at: z.string().min(1),
  reason: z.string().max(120).optional(),
});

const DeleteTimeOffInput = z.object({
  timeOffId: z.string().min(1),
});

/* ---------- server functions ---------- */

export const getCoverage = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => CoverageInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<CoverageReport>("/api/v1/advisors/coverage", {
      method: "GET",
      query: { days: String(data.days) },
      role: context.session.role,
    });
  });

export const getAdvisorWeek = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => AdvisorIdInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<AdvisorWeek>(
      `/api/v1/advisors/${encodeURIComponent(data.advisorId)}/schedule`,
      { method: "GET", role: context.session.role },
    );
  });

export const replaceSchedule = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => ReplaceScheduleInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<{ advisor_id: string; shifts: Shift[] }>(
      `/api/v1/advisors/${encodeURIComponent(data.advisorId)}/schedule`,
      { method: "PUT", body: { windows: data.windows }, role: context.session.role },
    );
  });

export const createTimeOff = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => CreateTimeOffInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<TimeOff>(`/api/v1/advisors/${encodeURIComponent(data.advisorId)}/time-off`, {
      method: "POST",
      body: {
        starts_at: data.starts_at,
        ends_at: data.ends_at,
        ...(data.reason ? { reason: data.reason } : {}),
      },
      role: context.session.role,
    });
  });

export const deleteTimeOff = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => DeleteTimeOffInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<{ deleted: boolean; time_off_id: string }>(
      `/api/v1/advisors/time-off/${encodeURIComponent(data.timeOffId)}`,
      { method: "DELETE", role: context.session.role },
    );
  });
