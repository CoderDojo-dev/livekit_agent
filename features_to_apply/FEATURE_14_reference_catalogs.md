# Cookbook 14 — Reference Catalogs (and the retirement of `/rules`)

**Branch of truth:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
**Apply onto:** local `version_80`
**Scope:** `Frontend/admin_dashboard/` + **two additive backend reads** (one repository method, one route)
**Depends on:** Feature 0 (substrate). No dependency on C9's `blocks.tsx` change — this page uses no stat cards.

---

## 0. Blocking decisions

### 0.1 — I was wrong about `/rules`, and the correction changes the outcome

Cookbook 7 §8.1 and Cookbook 13 §8.6 both recorded the same recommendation: *retire `/rules` because it duplicates `/policies`.* I made that call from the `/policies` side without re-reading the rules template. Having now read `src/routes/rules.tsx` (`44a50614`), **the premise is false.**

The page is titled **"Automation Rules"** and its description reads *"Trigger and action pairs that route, escalate and close work automatically."* Its columns are:

```
Rule | Trigger | Action | Runs (right) | Status
```

That is not the policy registry. `/policies` renders `reference.business_rules` — versioned deterministic thresholds like `RULE_BILLING_CAP` with `definition_json`, `version`, `active`. It has no concept of a trigger, an action, or a run count.

So `/rules` is not a duplicate. It is worse: it is a UI for an **automation engine that does not exist anywhere in the backend**. There is no trigger table, no action table, no run counter, no scheduler, no rule evaluator outside the deterministic policy gate. Building one is a subsystem, not an endpoint → **Constraint 3: flagged, never built.**

The distinction matters practically. "Duplicate page" invites a merge. "Page for an absent subsystem" permits only two honest moves: delete it, or repurpose the slot for something real.

### 0.2 — What is real, and has never been exposed

Reading `packages/persistence/src/persistence/models/reference.py` (`01b2a098`) to confirm the `/policies` side turned up the actual find. Its module docstring:

> *"Reference catalogs (spec section 13): **admin-managed, read-mostly shared data**. `business_rules` is the versioned, governable registry… error_catalog/products/recharge_catalog back agent-facing messages and plan/recharge information."*

The file declares **six** models. Cookbook 7 wired exactly one of them.

| Model | Table | Exposed today? | What it drives |
|---|---|---|---|
| `BusinessRule` | `reference.business_rules` | **yes** — C7 `/policies` | deterministic policy thresholds |
| `ErrorCatalog` | `reference.error_catalog` | **no** | every localized error the agent speaks (`fr`/`ar`/`en`) |
| `Product` | `reference.products` | **no** | the plan catalog behind `change_plan` |
| `RechargeCatalog` | `reference.recharge_catalog` | **no** | prepaid denominations behind `top_up` |
| `GeoArea` | `reference.geo_areas` | **no** | canonical Tunisian zones; FK target of `oss.outages.area_code` |
| `GeoAlias` | `reference.geo_aliases` | **no** | spoken/written forms that resolve to a zone |

The docstring calls this data **admin-managed**, and the admin console has never shown any of it. That is a genuine, load-bearing gap: an operator cannot currently answer *"what plans can the agent offer?"*, *"what does the agent actually say for error X in Arabic?"*, or *"is this town in our referential?"* — questions that determine live call behaviour.

**Decision: `/rules` is retired and its nav slot becomes `/reference` — the Reference Catalogs browser.** The absent automation engine is documented in §8.1 and left unbuilt.

### 0.3 — Read-only, and why that is the correct ceiling

"Admin-managed" invites CRUD. It does not get it here, for a reason that has now recurred four times (C5 `upsert_from_glpi`, C7 guardrails, C11 users, C12 personas):

- `GeoArea.area_code` is the **FK target of `oss.outages.area_code`**. The model comment states the design intent plainly: *"une panne ne PEUT donc plus nommer une zone inexistante… le problème #3 devient structurellement impossible grâce à la clé étrangère."* Editing or deactivating a zone from a dashboard risks the exact integrity failure the schema was designed to make impossible.
- `GeoAlias.normalized` is **computed at write time** (accents, Arabic diacritics and articles stripped, lowercased) and carries a unique constraint. A dashboard insert that skipped that normalization would silently break deterministic alias resolution — the lookup is a single indexed equality, so a mis-normalized row is simply never found.
- `Product.product_code` and `RechargeCatalog.code` are consumed by agent tools. Writing them is provisioning, not administration.

Writing these tables safely requires the normalization and validation logic to live server-side — which is new business logic. **Read-only ships; §8.2 records what a write path would have to guarantee.**

---

## 1. Backend reference (verbatim)

```python
class ErrorCatalog(UUIDPrimaryKey, Base):
    __tablename__ = "error_catalog"; __table_args__ = ({"schema": "reference"},)
    code:       Mapped[str]        # String(80), NOT NULL, unique
    domain:     Mapped[str | None] # String(40)
    message_fr: Mapped[str | None] # Text
    message_ar: Mapped[str | None] # Text
    message_en: Mapped[str | None] # Text
    created_at: Mapped[datetime]   # NOT NULL, now()

class Product(UUIDPrimaryKey, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("plan_type IN ('PREPAID','POSTPAID')", name="plan_type"),
                      {"schema": "reference"})
    product_code: Mapped[str]   # String(50), NOT NULL, unique
    name:         Mapped[str]   # String(120), NOT NULL
    plan_type:    Mapped[str]   # String(20), NOT NULL
    active:       Mapped[bool]  # NOT NULL, default true
    created_at:   Mapped[datetime]

class RechargeCatalog(UUIDPrimaryKey, Base):
    __tablename__ = "recharge_catalog"; __table_args__ = ({"schema": "reference"},)
    code:         Mapped[str]   # String(50), NOT NULL, unique
    amount:       Mapped[float] # Numeric(12,2), NOT NULL
    bonus_amount: Mapped[float] # Numeric(12,2), NOT NULL, default 0
    created_at:   Mapped[datetime]

class GeoArea(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "geo_areas"
    __table_args__ = (CheckConstraint("area_type IN ('governorate','delegation','locality')",
                      name="area_type"), {"schema": "reference"})
    area_code:   Mapped[str]        # String(40), NOT NULL, unique
    name_fr:     Mapped[str]        # String(120), NOT NULL
    name_ar:     Mapped[str | None] # String(120)
    name_en:     Mapped[str | None] # String(120)
    area_type:   Mapped[str]        # String(20), NOT NULL
    parent_code: Mapped[str | None] # FK reference.geo_areas.area_code  (self-referential)
    active:      Mapped[bool]       # NOT NULL, default true
```

**`Numeric(12,2)` — decimal units, not cents.** Cookbook 11 established the same for billing: `formatCurrency` from `format.ts` takes **cents** and must never be used here. Currency is TND (`currency_code String(3)` default `'TND'`).

**`Timestamps` mixin** on `GeoArea` supplies `created_at`/`updated_at`; `ErrorCatalog`, `Product` and `RechargeCatalog` declare `created_at` only — they have **no `updated_at`**. Do not render a "last modified" column for those three.

---

## 2. Backend additions (additive, read-only)

### 2.1 `repositories.py` — imports

The file currently imports only `BusinessRule` from reference. Extend that one line:

```python
from persistence.models.reference import BusinessRule, ErrorCatalog, GeoArea, Product, RechargeCatalog
```

`repositories.py` does **not** import `os` and this method does not need it (unlike C9's `analytics_trend`).

### 2.2 `repositories.py` — new method on `SupervisionRepository`

Place immediately after `business_rules()` so the reference reads sit together.

```python
    def reference_catalog(self, catalog: str, search: str = "", limit: int = 200) -> list[dict]:
        """Read one admin-managed reference catalog (spec section 13.1). Read-only."""
        limit = max(1, min(limit, 500))
        term = f"%{search.strip().lower()}%" if search and search.strip() else None

        if catalog == "errors":
            stmt = select(ErrorCatalog).order_by(ErrorCatalog.domain, ErrorCatalog.code)
            if term is not None:
                stmt = stmt.where(
                    func.lower(ErrorCatalog.code).like(term)
                    | func.lower(func.coalesce(ErrorCatalog.message_fr, "")).like(term)
                )
            return [
                {"code": r.code, "domain": r.domain, "message_fr": r.message_fr,
                 "message_ar": r.message_ar, "message_en": r.message_en}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "products":
            stmt = select(Product).order_by(Product.plan_type, Product.product_code)
            if term is not None:
                stmt = stmt.where(
                    func.lower(Product.product_code).like(term) | func.lower(Product.name).like(term)
                )
            return [
                {"product_code": r.product_code, "name": r.name,
                 "plan_type": r.plan_type, "active": r.active}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "recharges":
            stmt = select(RechargeCatalog).order_by(RechargeCatalog.amount)
            if term is not None:
                stmt = stmt.where(func.lower(RechargeCatalog.code).like(term))
            return [
                {"code": r.code, "amount": float(r.amount),
                 "bonus_amount": float(r.bonus_amount)}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "areas":
            stmt = select(GeoArea).order_by(GeoArea.area_type, GeoArea.name_fr)
            if term is not None:
                stmt = stmt.where(
                    func.lower(GeoArea.area_code).like(term)
                    | func.lower(GeoArea.name_fr).like(term)
                    | func.lower(func.coalesce(GeoArea.name_ar, "")).like(term)
                )
            return [
                {"area_code": r.area_code, "name_fr": r.name_fr, "name_ar": r.name_ar,
                 "name_en": r.name_en, "area_type": r.area_type,
                 "parent_code": r.parent_code, "active": r.active}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        return []
```

Notes:
- `func` and `select` are **already imported** at the top of `repositories.py`.
- `limit` is clamped 1–500, matching C10's clamp discipline. `geo_aliases` is deliberately **not** exposed — it is the largest table and is a lookup index, not a browsable catalog (§8.3).
- `float(r.amount)` mirrors the existing `float(i.total_amount)` in `customer_360`. Safe: both columns are `NOT NULL`.
- An unknown `catalog` returns `[]` rather than raising — the route validates first, so this is defence in depth.

### 2.3 `main.py` — new route

Insert **immediately after** `@app.get("/api/v1/reference/business-rules")`. No collision: both are static literal segments under `/reference/`, and neither is a path parameter, so FastAPI ordering is not sensitive here (unlike C11's `/customers` vs `/customers/{id}/360`).

```python
@app.get("/api/v1/reference/catalogs/{catalog}")
def reference_catalog(
    catalog: str,
    db: DbSession,
    _role: AdministrateurRole,
    search: str = "",
    limit: int = 200,
):
    if catalog not in {"errors", "products", "recharges", "areas"}:
        raise HTTPException(status_code=404, detail="unknown catalog")
    return SupervisionRepository(db).reference_catalog(catalog, search, limit)
```

**Role: `AdministrateurRole`**, matching the adjacent `/reference/business-rules` and `/jobs/*` routes. This is reference/governance data, not day-to-day supervision.

`HTTPException` is already imported in `main.py`. The 404 for an unknown catalog mirrors the existing `404 "customer not found"` / `404 "session not found"` convention.

**Justification against Constraint 3:** this is *access*, not new behaviour — a `SELECT` over existing tables with no writes, no new business rules, no derived semantics. Same class as C4 `session_list`, C8 `decision_ledger`, C9 `analytics_trend`, C10 `audit_entries`, C11 `customer_list`, C12 `agent_activity`.

---

## 3. Status vocabulary — twelfth chip trap, fourteenth clean cookbook

Only `Product.active` and `GeoArea.active` are booleans. Cookbook 7 already established the mapping and it applies unchanged:

| Backend | Mapped to |
|---|---|
| `active = true` | `active` |
| `active = false` | `inactive` |

Everything else on this page is **not a status** and gets **no chip**:
- `plan_type` (`PREPAID`/`POSTPAID`) → `Token`. It is a category. Note it is **UPPERCASE**, same as `Subscription.plan_type` in C11.
- `area_type` (`governorate`/`delegation`/`locality`) → `Token`.
- `domain` on errors → `Token`, open `String(40)` vocabulary.

`StatusChip` returns `null` for unmapped keys, so routing any of these through it would render **blank cells**. 

**Zero changes to `status.ts`. Fourteenth consecutive cookbook.**

---

## 4. Files

**New**
- `src/lib/api/reference.server.ts`
- `src/lib/nexus/reference-view.ts`
- `src/routes/reference.tsx`

**Modified**
- `src/lib/nexus/query-keys.ts` — `+ referenceKeys`
- `src/lib/nexus/nav.ts` — `/rules` entry → `/reference`, `PAGE_META`, shortcut `G R`
- `src/lib/nexus/data.ts` — remove `RULES` (and its row type)
- `routeTree.gen.ts` — regenerated

**Deleted**
- `src/routes/rules.tsx`

**Backend**
- `apps/business-api/src/business_api/repositories.py` — one import line + one method
- `apps/business-api/src/business_api/main.py` — one route

---

## 5. Code

### 5.1 `src/lib/api/reference.server.ts`

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/client";
import { authedMiddleware, inputValidator, requireRole } from "@/lib/api/middleware";

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

/** Must stay in sync with the server-side whitelist; anything else is a 404. */
export const catalogKind = z.enum(["errors", "products", "recharges", "areas"]);
export type CatalogKind = z.infer<typeof catalogKind>;

export const getReferenceCatalog = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("administrateur")])
  .inputValidator(
    inputValidator(
      z.object({
        catalog: catalogKind,
        search: z.string().max(120).default(""),
      }),
    ),
  )
  .handler(async ({ data, context }) => {
    const rows = await businessApi<CatalogRow[]>(
      `/api/v1/reference/catalogs/${data.catalog}`,
      {
        method: "GET",
        query: { search: data.search, limit: 200 },
        role: context.session.role,
      },
    );
    return Array.isArray(rows) ? rows : [];
  });
```

`requireRole("administrateur")` — the **factory** form (Feature 2 correction #1), matching the route's `AdministrateurRole`. `GET`, so the React Start CSRF/POST rule (Feature 2 correction #2) does not apply.

### 5.2 `src/lib/nexus/reference-view.ts`

```ts
import type { CatalogKind } from "@/lib/api/reference.server";

export const CATALOG_TABS: Array<{ value: CatalogKind; label: string }> = [
  { value: "errors", label: "Error messages" },
  { value: "products", label: "Plans" },
  { value: "recharges", label: "Recharges" },
  { value: "areas", label: "Geo areas" },
];

export const CATALOG_SUBTITLE: Record<CatalogKind, string> = {
  errors: "What the agent says to a caller when something fails, per language.",
  products: "The plan catalog the agent can offer and switch a subscriber to.",
  recharges: "Prepaid denominations and their bonus amounts.",
  areas: "Canonical Tunisian zones. Outages can only reference a zone listed here.",
};

/** active -> canonical status.ts key (Cookbook 7 mapping, unchanged). */
export function activeStatusKey(active: boolean): string {
  return active ? "active" : "inactive";
}

/**
 * Numeric(12,2) is DECIMAL UNITS, not cents.
 * format.ts formatCurrency() takes cents and must never be used here (Cookbook 11).
 */
export function formatAmount(value: number): string {
  return `${value.toFixed(2)} TND`;
}

const AREA_TYPE_LABEL: Record<string, string> = {
  governorate: "Governorate",
  delegation: "Delegation",
  locality: "Locality",
};

/** CheckConstraint allows three values; unknown passes through verbatim. */
export function areaTypeLabel(t: string): string {
  return AREA_TYPE_LABEL[t] ?? t;
}

/** Nullable Text columns: never render "null". */
export function orDash(v: string | null | undefined): string {
  return v && v.trim() ? v : "—";
}
```

No `new Date`, no `getDay`, no `getHours`, no `toLocaleString`. The endpoint returns no timestamps at all, so the date trap is structurally absent — same as Cookbook 13.

### 5.3 `src/lib/nexus/query-keys.ts` (additive)

```ts
export const referenceKeys = {
  all: ["reference"] as const,
  catalog: (catalog: string, search: string) =>
    ["reference", "catalog", catalog, search] as const,
};
```

### 5.4 `src/lib/nexus/nav.ts`

Replace the `/rules` entry **in place** — same section, same position, no reordering:

```ts
{ label: "Reference", to: "/reference", icon: Library, shortcut: "G R" },
```

`PAGE_META`:

```ts
"/reference": {
  title: "Reference",
  subtitle: "Admin-managed catalogs the agent reads at runtime.",
},
```

Remove the `"/rules"` key from both. Shortcut `G R` is free (`G A` Advisors, `G D` Availability, `G K` Decisions, `G E` Escalations are taken). If `Library` is not already imported from `lucide-react` elsewhere, prefer reusing the icon the `/rules` entry already carried rather than introducing a new one.

### 5.5 `src/routes/reference.tsx`

```tsx
import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Library } from "lucide-react";
import {
  EmptyState,
  SearchInput,
  StatusChip,
  TableShell,
  Tabs,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import {
  getReferenceCatalog,
  type AreaEntry,
  type CatalogKind,
  type ErrorEntry,
  type ProductEntry,
  type RechargeEntry,
} from "@/lib/api/reference.server";
import {
  activeStatusKey,
  areaTypeLabel,
  CATALOG_SUBTITLE,
  CATALOG_TABS,
  formatAmount,
  orDash,
} from "@/lib/nexus/reference-view";
import { referenceKeys } from "@/lib/nexus/query-keys";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/reference")({
  head: () => ({
    meta: [
      { title: "Reference — Nexus" },
      {
        name: "description",
        content: "Admin-managed catalogs the agent reads at runtime: errors, plans, recharges, zones.",
      },
      { property: "og:title", content: "Reference — Nexus" },
      { property: "og:description", content: "Error messages, plans, recharges and geo areas." },
    ],
  }),
  component: ReferencePage,
});

/** Column count per catalog — used for skeleton and error colSpan. */
const COLS: Record<CatalogKind, number> = {
  errors: 5,
  products: 4,
  recharges: 3,
  areas: 5,
};

function ReferencePage() {
  const [catalog, setCatalog] = useState<CatalogKind>("errors");
  const [search, setSearch] = useState("");

  const query = useQuery({
    queryKey: referenceKeys.catalog(catalog, search),
    queryFn: () => getReferenceCatalog({ data: { catalog, search } }),
  });

  const rows = query.data ?? [];
  const cols = COLS[catalog];

  const head = useMemo(() => {
    if (catalog === "errors") {
      return (
        <tr>
          <Th>Code</Th>
          <Th>Domain</Th>
          <Th>Français</Th>
          <Th>العربية</Th>
          <Th>English</Th>
        </tr>
      );
    }
    if (catalog === "products") {
      return (
        <tr>
          <Th>Product</Th>
          <Th>Name</Th>
          <Th>Plan type</Th>
          <Th>Status</Th>
        </tr>
      );
    }
    if (catalog === "recharges") {
      return (
        <tr>
          <Th>Code</Th>
          <Th align="right">Amount</Th>
          <Th align="right">Bonus</Th>
        </tr>
      );
    }
    return (
      <tr>
        <Th>Area</Th>
        <Th>Name</Th>
        <Th>Type</Th>
        <Th>Parent</Th>
        <Th>Status</Th>
      </tr>
    );
  }, [catalog]);

  return (
    <PageSection>
      <TableShell
        toolbar={
          <>
            <Tabs
              items={CATALOG_TABS.map((t) => ({ label: t.label, value: t.value }))}
              value={catalog}
              onChange={(v: string) => {
                setCatalog(v as CatalogKind);
                setSearch("");
              }}
            />
            <SearchInput
              placeholder="Search this catalog"
              className="ml-auto w-[260px]"
              value={search}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value)}
            />
          </>
        }
        head={head}
        footer={
          <span className="t-caption text-ink-4">
            {CATALOG_SUBTITLE[catalog]}
          </span>
        }
      >
        {query.isPending ? (
          <TableSkeleton rows={8} cols={cols} />
        ) : query.isError ? (
          <TableErrorRow
            colSpan={cols}
            message={errorMessage(query.error)}
            onRetry={() => void query.refetch()}
          />
        ) : rows.length === 0 ? (
          <tr>
            <Td colSpan={cols}>
              <EmptyState
                icon={Library}
                title={search ? "No match in this catalog" : "This catalog is empty"}
                description={
                  search
                    ? "No entry matches that term."
                    : "Nothing has been loaded into this reference table yet."
                }
              />
            </Td>
          </tr>
        ) : catalog === "errors" ? (
          (rows as ErrorEntry[]).map((r) => (
            <tr key={r.code} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td><span className="t-mono text-ink-1">{r.code}</span></Td>
              <Td>{r.domain ? <Token>{r.domain}</Token> : <span className="t-caption text-ink-5">—</span>}</Td>
              <Td><span className="t-ui text-ink-2">{orDash(r.message_fr)}</span></Td>
              <Td><span className="t-ui text-ink-2" dir="rtl">{orDash(r.message_ar)}</span></Td>
              <Td><span className="t-ui text-ink-2">{orDash(r.message_en)}</span></Td>
            </tr>
          ))
        ) : catalog === "products" ? (
          (rows as ProductEntry[]).map((r) => (
            <tr key={r.product_code} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td><span className="t-mono text-ink-1">{r.product_code}</span></Td>
              <Td><span className="t-ui text-ink-1">{r.name}</span></Td>
              <Td><Token>{r.plan_type}</Token></Td>
              <Td><StatusChip status={activeStatusKey(r.active)} /></Td>
            </tr>
          ))
        ) : catalog === "recharges" ? (
          (rows as RechargeEntry[]).map((r) => (
            <tr key={r.code} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td><span className="t-mono text-ink-1">{r.code}</span></Td>
              <Td align="right"><span className="t-mono-l text-ink-1">{formatAmount(r.amount)}</span></Td>
              <Td align="right">
                <span className="t-mono text-ink-3">
                  {r.bonus_amount > 0 ? formatAmount(r.bonus_amount) : "—"}
                </span>
              </Td>
            </tr>
          ))
        ) : (
          (rows as AreaEntry[]).map((r) => (
            <tr key={r.area_code} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td><span className="t-mono text-ink-1">{r.area_code}</span></Td>
              <Td>
                <span className="t-ui block truncate text-ink-1">{r.name_fr}</span>
                {r.name_ar ? (
                  <span className="t-caption block truncate text-ink-4" dir="rtl">{r.name_ar}</span>
                ) : null}
              </Td>
              <Td><Token>{areaTypeLabel(r.area_type)}</Token></Td>
              <Td>
                {r.parent_code ? (
                  <span className="t-mono text-ink-3">{r.parent_code}</span>
                ) : (
                  <span className="t-caption text-ink-5">—</span>
                )}
              </Td>
              <Td><StatusChip status={activeStatusKey(r.active)} /></Td>
            </tr>
          ))
        )}
      </TableShell>
    </PageSection>
  );
}
```

**Design-system compliance.** `TableShell` / `Th` / `Td` / `Token` / `StatusChip` / `Tabs` / `SearchInput` are all existing primitives, and the row hover class `transition-colors duration-[120ms] hover:bg-surface-3` is lifted verbatim from the retired `rules.tsx`. The **"New rule" button is removed, not disabled** — Cookbook 5's precedent: a disabled control implies a permission problem, an absent control states correctly that the capability does not exist.

**Arabic columns carry `dir="rtl"`.** This is a correctness fix, not a style change: without it, mixed Arabic/Latin strings render with punctuation in the wrong place. It introduces no new token, colour or class.

**Call-site checks (carried forward):** `Tabs` may not accept `items/value/onChange` in that shape, `SearchInput` may not forward `value`/`onChange`, and `Td`/`Th` may not forward `colSpan`/`align`. All four are verified in Checks 4–5 and adjusted to real signatures at apply time — this bit us in Feature 1.

---

## 6. Open items

### 6.1 The automation engine does not exist

`/rules` promised trigger→action automation with run counts. Nothing in the backend implements it: no trigger registry, no action dispatcher, no run counter, no scheduler. The nearest real things are the **deterministic policy gate** (`/policies`, C7) and the **action ledger** (`/decisions`, C8) — both of which record what happened, neither of which lets an admin define a new automation.

Building it is a subsystem: rule storage, a safe evaluation model, an execution path with idempotency, and an audit story. **Constraint 3 forbids it and I am not drafting it.** If you want it, it needs its own scoping conversation, not a cookbook.

### 6.2 If these catalogs should be editable

Read-only ships (§0.3). A write path would have to guarantee, server-side:
- `GeoAlias.normalized` computed with the **same** normalization the resolver uses — accents, Arabic diacritics, articles, lowercase. A client-side implementation would drift and silently break lookups.
- `GeoArea` deactivation checked against `oss.outages.area_code` referents before it is allowed.
- `Product.product_code` / `RechargeCatalog.code` validated against whatever the provisioning adapters expect.

Each is business logic. Tell me if you want it scoped and I will treat it as its own feature.

### 6.3 `geo_aliases` is deliberately not exposed

It is the largest reference table and functions as a lookup index rather than a browsable catalog. If operators need *"why did the agent not recognise this town?"*, the right surface is a **resolver probe** — type a spoken form, see which `area_code` it resolves to — not a 10k-row table. That is a small, genuinely useful feature and I would scope it separately.

### 6.4 No `updated_at` on three of the four

`GeoArea` has the `Timestamps` mixin; `ErrorCatalog`, `Product` and `RechargeCatalog` have `created_at` only. So "when did this plan change?" is unanswerable for the catalogs where it matters most. Adding the mixin is a migration, not an endpoint — flagged, not done. Same shape as C6's `updated_at` gap on `DocumentSummary`.

### 6.5 Role choice

I put this behind `administrateur` to match the adjacent `/reference/business-rules`. Arguably a `superviseur` should be able to *read* the error catalog and plan list — they are not sensitive. Say the word and it drops one rank; C7 §8.2 raised the identical question about `/policies` and is still open.

---

## 7. Validation checklist

1. `bunx tsc --noEmit` → clean.
2. `bun run lint` → exactly **36 problems** (28 prettier errors + 8 warnings).
3. `bun run build` → exit 0.
4. `grep -n "export function Tabs\|export function SearchInput" -A 12 src/components/nexus/primitives.tsx` → confirm real prop shapes; adjust call sites.
5. `grep -n "export function Td\|export function Th" -A 8 src/components/nexus/primitives.tsx` → confirm `colSpan` and `align` are forwarded.
6. `grep -rn "RULES" src/` → zero hits after deletion.
7. `grep -rn "/rules" src/` → zero hits (nav, routeTree, links).
8. `git diff -- src/lib/nexus/status.ts` → empty. **Fourteenth consecutive cookbook.**
9. `git diff --stat -- Frontend/admin_dashboard/package.json` → empty. Zero new dependencies.
10. `git diff --stat -- apps/ packages/` → exactly **two** files: `repositories.py`, `main.py`.
11. `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/reference.tsx src/lib/nexus/reference-view.ts` → no hits.
12. `grep -n 'getDay(\|getHours(\|new Date(\|toLocaleString(' src/routes/reference.tsx src/lib/nexus/reference-view.ts` → no hits.
13. `grep -n "formatCurrency" src/lib/nexus/reference-view.ts src/routes/reference.tsx` → **zero hits** (it takes cents; amounts here are decimal units).
14. `curl -s -H 'X-Role: administrateur' 'localhost:8108/api/v1/reference/catalogs/errors' | head -c 400` → JSON array.
15. `curl -s -o /dev/null -w '%{http_code}' -H 'X-Role: administrateur' 'localhost:8108/api/v1/reference/catalogs/nope'` → **404**.
16. `curl -s -o /dev/null -w '%{http_code}' -H 'X-Role: superviseur' 'localhost:8108/api/v1/reference/catalogs/errors'` → **403**.
17. `curl -s 'localhost:8108/api/v1/reference/catalogs/recharges?limit=99999' | jq 'length'` → ≤ **500** (clamp holds).
18. Navigate `/reference` → Errors tab active by default, rows render, Arabic column renders RTL.
19. Switch tabs → headers and column count change together; search box **clears** on tab change (no stale term filtering a different catalog).
20. Type a nonsense term → "No match in this catalog" EmptyState with the correct `colSpan`, no layout break.
21. Seed a product with `active = false` → chip renders **inactive**, never blank. Repeat with `true`.
22. Seed an error row with `message_ar = NULL` → renders `—`, never `null`.
23. Seed a recharge with `bonus_amount = 0` → renders `—`, not `0.00 TND`.
24. Seed a governorate with `parent_code = NULL` → renders `—`.
25. Network tab → all requests go to the proxy origin, **zero** direct requests to `:8108`.
26. Log in as `conseiller` → forbidden state from the substrate, no retry storm (QueryClient retries false on 401/403).
