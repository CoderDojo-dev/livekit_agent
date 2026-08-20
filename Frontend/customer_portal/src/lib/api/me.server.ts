import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

type Me = {
  subject: string;
  /** Principal.kind in infrastructure/auth/principal.py. "service" is the
   * X-API-Key machine principal; it can never reach the portal, but the type
   * must not lie about what the endpoint can return. */
  kind: "staff" | "client" | "service";
  role: string;
  account_id: string | null;
  customer_id: string | null;
};

/**
 * The controller endpoint-the only one used by the customer portal to confirm WHO the bearer
 * is. The backend reads the identity from the token, never from the request body or headers.
 */
export const fetchMe = createServerFn({ method: "GET" }).handler(async (): Promise<Me | null> => {
  try {
    return await businessApi<Me>("/api/v1/auth/me", {});
  } catch {
    return null;
  }
});

export type ProfileDetail = {
  customer_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  preferred_language: string;
  region: string | null;
  city: string | null;
  address_lines: string[];
  account_number: string | null;
  customer_since: string | null;
  status: string;
  plan: string | null;
  msisdn: string | null;
};

export const fetchProfileDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<ProfileDetail> =>
    businessApi<ProfileDetail>("/api/v1/me/profile/detail", {}),
  );

export type Subscription360 = {
  subscription_id: string;
  msisdn: string | null;
  plan: string | null;
  status: string | null;
};

export type Customer360 = {
  customer_id: string;
  name: string;
  preferred_language: string;
  subscriptions: Subscription360[];
  open_invoices: {
    invoice: string;
    amount: number;
    outstanding: number;
    status: string;
  }[];
  tickets: { glpi_id: string | null; status: string; subject: string | null }[];
};

/** GET /api/v1/me/profile — the signed-in customer's own 360 (customer_360). */
export const fetchProfile360 = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<Customer360> => businessApi<Customer360>("/api/v1/me/profile", {}));

/**
 * The three languages the assistant can hold a conversation in.
 *
 * Not a UI invention: this is the crm.customers CHECK constraint
 * (`preferred_language IN ('fr','ar','en')`) and agent-worker's
 * SUPPORTED_LANGUAGES, which are the languages with an STT/TTS preset.
 */
export const AGENT_LANGUAGES = ["fr", "ar", "en"] as const;
export type AgentLanguage = (typeof AGENT_LANGUAGES)[number];

/** The platform default when nothing else applies (agent-worker DEFAULT_LANGUAGE). */
export const DEFAULT_AGENT_LANGUAGE: AgentLanguage = "fr";

export function isAgentLanguage(value: string | null | undefined): value is AgentLanguage {
  return AGENT_LANGUAGES.includes(value as AgentLanguage);
}

/**
 * PUT /api/v1/me/profile/language
 *
 * Writes crm.customers.preferred_language — the column the agent worker
 * already reads as the *saved preference* candidate. It does not set the
 * language of a live conversation and it does not outrank an explicit
 * in-conversation request; the precedence lives in agent-worker
 * config/language_policy.resolve_session_language and is not duplicated here.
 */
export const setPreferredLanguage = createServerFn({ method: "POST" })
  .middleware([authedMiddleware])
  .validator(z.object({ language: z.enum(AGENT_LANGUAGES) }))
  .handler(async ({ data }): Promise<{ preferred_language: AgentLanguage; changed: boolean }> =>
    businessApi("/api/v1/me/profile/language", {
      method: "PUT",
      body: { language: data.language },
    }),
  );
