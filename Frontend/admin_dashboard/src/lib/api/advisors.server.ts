import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";
import { businessApi } from "@/lib/api/business-api";

/* ---------- Types: the exact shape of business_api.advisors.to_dict() ---------- */

export type AdvisorStatus = "available" | "busy" | "offline";

export type Advisor = {
  id: string;
  full_name: string;
  email: string | null;
  phone_e164: string | null;
  sip_uri: string | null;
  skills: string[];
  language: string;
  status: AdvisorStatus;
  max_concurrent_calls: number;
  active_calls: number;
  is_on_call: boolean;
  is_active: boolean;
};

/* ---------- Input schemas ----------
 * Mirrors AdvisorPayload (main.py). Empty strings are meaningful and are NOT
 * stripped: main.py uses model_dump(exclude_none=True), so null cannot clear a
 * field — only "" can. See cookbook section 2.4.
 */

const advisorFields = {
  full_name: z.string().trim().min(1, "Name is required").max(120),
  email: z.string().trim().max(255),
  phone_e164: z.string().trim().max(20),
  sip_uri: z.string().trim().max(255),
  skills: z.array(z.string().trim().min(1)).max(20),
  language: z.string().trim().min(1).max(10),
  status: z.enum(["available", "busy", "offline"]),
  max_concurrent_calls: z.number().int().min(1),
  is_on_call: z.boolean(),
  is_active: z.boolean(),
};

const CreateInput = z.object(advisorFields);
const UpdateInput = z
  .object({ id: z.string().min(1) })
  .extend(z.object(advisorFields).partial().shape);
const IdInput = z.object({ id: z.string().min(1) });
const ListInput = z.object({ includeInactive: z.boolean().default(false) });

export type AdvisorCreateInput = z.infer<typeof CreateInput>;
export type AdvisorUpdateInput = z.infer<typeof UpdateInput>;

/* ---------- Server functions ----------
 * Authorization is enforced here, in the middleware of the endpoint that
 * touches the data — not in beforeLoad. Server functions are reachable
 * independently of the route that renders them.
 */

export const listAdvisors = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) => {
    const res = await businessApi<{ advisors: Advisor[] }>("/api/v1/advisors", {
      method: "GET",
      query: { include_inactive: data.includeInactive },
      role: context.session.role,
    });
    return res.advisors;
  });

export const createAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => CreateInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<Advisor>("/api/v1/advisors", {
      method: "POST",
      body: data,
      role: context.session.role,
    }),
  );

export const updateAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => UpdateInput.parse(data))
  .handler(async ({ data, context }) => {
    const { id, ...patch } = data;
    return businessApi<Advisor>(`/api/v1/advisors/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: patch,
      role: context.session.role,
    });
  });

export const deleteAdvisor = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => IdInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<{ deleted: boolean; advisor_id: string }>(
      `/api/v1/advisors/${encodeURIComponent(data.id)}`,
      { method: "DELETE", role: context.session.role },
    ),
  );
