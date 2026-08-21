import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type ErrorEntry = {
  code: string;
  domain: string | null;
  message_fr: string | null;
  message_ar: string | null;
  message_en: string | null;
};

export type ProductEntry = {
  product_code: string;
  name: string;
  plan_type: string;
  active: boolean;
};

export type RechargeEntry = {
  code: string;
  amount: number;
  bonus_amount: number;
};

export type AreaEntry = {
  area_code: string;
  name_fr: string;
  name_ar: string | null;
  name_en: string | null;
  area_type: string;
  parent_code: string | null;
  active: boolean;
};

export type CatalogRow = ErrorEntry | ProductEntry | RechargeEntry | AreaEntry;

export const CATALOG_KINDS = ["errors", "products", "recharges", "areas"] as const;
export type CatalogKind = (typeof CATALOG_KINDS)[number];

export const getReferenceCatalog = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { catalog?: unknown; search?: unknown };
    const catalog = typeof input.catalog === "string" ? input.catalog : "";
    const search = typeof input.search === "string" ? input.search.slice(0, 120) : "";
    if (!CATALOG_KINDS.includes(catalog as CatalogKind)) {
      throw new Error("unknown catalog");
    }
    return { catalog: catalog as CatalogKind, search };
  })
  .handler(async ({ data, context }) => {
    const rows = await businessApi<CatalogRow[]>(`/api/v1/reference/catalogs/${data.catalog}`, {
      method: "GET",
      query: { search: data.search, limit: 200 },
      role: context.session.role,
    });
    return Array.isArray(rows) ? rows : [];
  });

/* =============================================================================================
 * Catalog writes + outages
 *
 * These catalogs are RUNTIME INPUTS, unlike the policy registry: the agent reads products,
 * recharges and geo areas while a caller is on the line, so an edit here changes what the agent
 * can offer — and what it knows about the network — on the very next call. That is the point of
 * exposing them, and the reason every mutation is administrateur-only and audited server-side.
 *
 * The backend enforces the invariants that keep the agent coherent, and this layer surfaces its
 * refusals verbatim rather than guessing:
 *   - a plan a subscription points at cannot be deleted, only deactivated;
 *   - a geo area with children or outages cannot be deleted (oss.outages.area_code is a foreign
 *     key into it, and orphaning that is what the geo referential exists to prevent);
 *   - an outage must name a real area, carry a known cause, and have a FRENCH description —
 *     without one the agent can detect the incident but has nothing to say about it.
 * ========================================================================================== */

export type OutageEntry = {
  id: string;
  area_code: string | null;
  area_name: string | null;
  area: string | null;
  region: string | null;
  severity: string;
  cause: string | null;
  affected_services: string | null;
  resolved: boolean;
  start_time: string | null;
  end_time: string | null;
  description_fr: string | null;
  description_ar: string | null;
  description_en: string | null;
};

/** Mirrors the ck_outages_cause CHECK constraint. Note the spelling: "fiber_cut", not "fibre". */
export const OUTAGE_CAUSES = [
  "fiber_cut",
  "power_failure",
  "equipment_failure",
  "planned_maintenance",
  "congestion",
  "weather",
  "third_party_damage",
] as const;

export const OUTAGE_SEVERITIES = ["minor", "major", "critical"] as const;

export const listOutages = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((raw: unknown) => {
    const input = (raw ?? {}) as { activeOnly?: unknown };
    return { activeOnly: input.activeOnly === true };
  })
  .handler(async ({ data, context }) =>
    businessApi<{ outages: OutageEntry[] }>("/api/v1/outages", {
      method: "GET",
      query: { active_only: data.activeOnly, limit: 200 },
      role: context.session.role,
    }),
  );

const OutageCreate = z.object({
  areaCode: z.string().trim().min(1).max(40),
  severity: z.enum(OUTAGE_SEVERITIES),
  cause: z.enum(OUTAGE_CAUSES).optional(),
  affectedServices: z.string().trim().max(120).optional(),
  descriptionFr: z.string().trim().min(1),
  descriptionAr: z.string().trim().optional(),
  descriptionEn: z.string().trim().optional(),
});

export const createOutage = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => OutageCreate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<{ id: string }>("/api/v1/outages", {
      method: "POST",
      body: {
        area_code: data.areaCode,
        severity: data.severity,
        ...(data.cause ? { cause: data.cause } : {}),
        ...(data.affectedServices ? { affected_services: data.affectedServices } : {}),
        description_fr: data.descriptionFr,
        ...(data.descriptionAr ? { description_ar: data.descriptionAr } : {}),
        ...(data.descriptionEn ? { description_en: data.descriptionEn } : {}),
      },
      role: context.session.role,
    }),
  );

const OutageUpdate = z.object({
  outageId: z.string().min(1),
  severity: z.enum(OUTAGE_SEVERITIES).optional(),
  resolved: z.boolean().optional(),
  descriptionFr: z.string().trim().optional(),
  descriptionAr: z.string().trim().optional(),
  descriptionEn: z.string().trim().optional(),
});

export const updateOutage = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => OutageUpdate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<OutageEntry>(`/api/v1/outages/${encodeURIComponent(data.outageId)}`, {
      method: "PATCH",
      body: {
        ...(data.severity ? { severity: data.severity } : {}),
        ...(data.resolved === undefined ? {} : { resolved: data.resolved }),
        ...(data.descriptionFr ? { description_fr: data.descriptionFr } : {}),
        ...(data.descriptionAr === undefined ? {} : { description_ar: data.descriptionAr }),
        ...(data.descriptionEn === undefined ? {} : { description_en: data.descriptionEn }),
      },
      role: context.session.role,
    }),
  );

/* ------------------------------------------------------------------------------ plans ----- */

const ProductCreate = z.object({
  productCode: z.string().trim().min(1).max(50),
  name: z.string().trim().min(1).max(120),
  planType: z.enum(["PREPAID", "POSTPAID"]),
});

export const createProduct = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => ProductCreate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<ProductEntry>("/api/v1/reference/products", {
      method: "POST",
      body: { product_code: data.productCode, name: data.name, plan_type: data.planType },
      role: context.session.role,
    }),
  );

const ProductUpdate = z.object({
  productCode: z.string().min(1),
  name: z.string().trim().max(120).optional(),
  planType: z.enum(["PREPAID", "POSTPAID"]).optional(),
  active: z.boolean().optional(),
});

export const updateProduct = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => ProductUpdate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<ProductEntry>(
      `/api/v1/reference/products/${encodeURIComponent(data.productCode)}`,
      {
        method: "PATCH",
        body: {
          ...(data.name ? { name: data.name } : {}),
          ...(data.planType ? { plan_type: data.planType } : {}),
          ...(data.active === undefined ? {} : { active: data.active }),
        },
        role: context.session.role,
      },
    ),
  );

export const deleteProduct = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => z.object({ productCode: z.string().min(1) }).parse(data))
  .handler(async ({ data, context }) =>
    businessApi<void>(`/api/v1/reference/products/${encodeURIComponent(data.productCode)}`, {
      method: "DELETE",
      role: context.session.role,
    }),
  );

/* -------------------------------------------------------------------------- recharges ----- */

const RechargeCreate = z.object({
  code: z.string().trim().min(1).max(50),
  amount: z.number().positive(),
  bonusAmount: z.number().min(0),
});

export const createRecharge = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => RechargeCreate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<RechargeEntry>("/api/v1/reference/recharges", {
      method: "POST",
      body: { code: data.code, amount: data.amount, bonus_amount: data.bonusAmount },
      role: context.session.role,
    }),
  );

const RechargeUpdate = z.object({
  code: z.string().min(1),
  amount: z.number().positive().optional(),
  bonusAmount: z.number().min(0).optional(),
});

export const updateRecharge = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => RechargeUpdate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<RechargeEntry>(`/api/v1/reference/recharges/${encodeURIComponent(data.code)}`, {
      method: "PATCH",
      body: {
        ...(data.amount === undefined ? {} : { amount: data.amount }),
        ...(data.bonusAmount === undefined ? {} : { bonus_amount: data.bonusAmount }),
      },
      role: context.session.role,
    }),
  );

export const deleteRecharge = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => z.object({ code: z.string().min(1) }).parse(data))
  .handler(async ({ data, context }) =>
    businessApi<void>(`/api/v1/reference/recharges/${encodeURIComponent(data.code)}`, {
      method: "DELETE",
      role: context.session.role,
    }),
  );

/* -------------------------------------------------------------------------- geo areas ----- */

const AreaCreate = z.object({
  areaCode: z.string().trim().min(1).max(40),
  nameFr: z.string().trim().min(1).max(120),
  areaType: z.enum(["governorate", "delegation", "locality"]),
  parentCode: z.string().trim().max(40).optional(),
});

export const createGeoArea = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => AreaCreate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<AreaEntry>("/api/v1/reference/geo-areas", {
      method: "POST",
      body: {
        area_code: data.areaCode,
        name_fr: data.nameFr,
        area_type: data.areaType,
        ...(data.parentCode ? { parent_code: data.parentCode } : {}),
      },
      role: context.session.role,
    }),
  );

const AreaUpdate = z.object({
  areaCode: z.string().min(1),
  nameFr: z.string().trim().max(120).optional(),
  active: z.boolean().optional(),
});

export const updateGeoArea = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => AreaUpdate.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<AreaEntry>(`/api/v1/reference/geo-areas/${encodeURIComponent(data.areaCode)}`, {
      method: "PATCH",
      body: {
        ...(data.nameFr ? { name_fr: data.nameFr } : {}),
        ...(data.active === undefined ? {} : { active: data.active }),
      },
      role: context.session.role,
    }),
  );

export const deleteGeoArea = createServerFn({ method: "POST" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator((data: unknown) => z.object({ areaCode: z.string().min(1) }).parse(data))
  .handler(async ({ data, context }) =>
    businessApi<void>(`/api/v1/reference/geo-areas/${encodeURIComponent(data.areaCode)}`, {
      method: "DELETE",
      role: context.session.role,
    }),
  );
