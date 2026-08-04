import { createServerFn } from "@tanstack/react-start";
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
