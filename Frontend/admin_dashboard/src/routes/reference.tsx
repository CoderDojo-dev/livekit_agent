import { useEffect, useMemo, useState } from "react";
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
import { pageTitle } from "@/lib/nexus/brand";
import { PageSection } from "@/components/nexus/app-topbar";
import { OutageManager } from "@/components/nexus/outage-manager";
import { CatalogCreateButton, CatalogRowActions } from "@/components/nexus/catalog-edit";
import { SectionHeading } from "@/components/nexus/blocks";
import { Route as RootRoute } from "@/routes/__root";
import { hasRank } from "@/lib/api/session";
import { RadioTower, Library as LibraryIcon } from "lucide-react";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
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
  DEFAULT_CATALOG,
  formatAmount,
  orDash,
} from "@/lib/nexus/reference-view";
import { referenceKeys } from "@/lib/nexus/query-keys";
import { errorMessage } from "@/lib/api/errors";

export const Route = createFileRoute("/reference")({
  head: () => ({
    meta: [
      { title: pageTitle("Reference") },
      {
        name: "description",
        content:
          "Admin-managed catalogs the agent reads at runtime: errors, plans, recharges, zones.",
      },
      { property: "og:title", content: pageTitle("Reference") },
      {
        property: "og:description",
        content: "Error messages, plans, recharges and geo areas.",
      },
    ],
  }),
  component: ReferencePage,
});

/** Column count per catalog — used for skeleton and error colSpan. */
/* Column counts INCLUDE the trailing action column on the three editable catalogs. Error
 * messages have no write endpoint (they are managed upstream), so that catalog keeps its width. */
const COLS: Record<CatalogKind, number> = {
  errors: 5,
  products: 5,
  recharges: 4,
  areas: 6,
};

function ReferencePage() {
  const { session } = RootRoute.useRouteContext();
  const canEdit = session !== null && hasRank(session, "administrateur");

  const [catalog, setCatalog] = useState<CatalogKind>(DEFAULT_CATALOG);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const query = useQuery({
    queryKey: referenceKeys.catalog(catalog, search),
    queryFn: () => getReferenceCatalog({ data: { catalog, search } }),
  });

  const rows = query.data ?? [];

  /* Catalogs run to thousands of rows (error codes, areas) and every one of them used to
   * render at once, which made /reference among the tallest pages in the product. */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 420,
    min: 6,
    max: 16,
    fallback: 10,
  });

  useEffect(() => setPage(0), [catalog, search, pageSize]);
  const safePage = clampPage(page, rows.length, pageSize);
  const pageRows = slicePage(rows, safePage, pageSize);
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
          <Th align="right" />
        </tr>
      );
    }
    if (catalog === "recharges") {
      return (
        <tr>
          <Th>Code</Th>
          <Th align="right">Amount</Th>
          <Th align="right">Bonus</Th>
          <Th align="right" />
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
        <Th align="right" />
      </tr>
    );
  }, [catalog]);

  return (
    <>
      <PageSection index={0}>
        <SectionHeading
          title="Catalogs"
          hint="Read by the agent during a call"
          icon={LibraryIcon}
        />
        <TableShell
          minWidth={860}
          bodyAsChild
          busy={query.isFetching && !query.isPending}
          toolbar={
            <>
              <Tabs
                groupId="reference-catalog"
                items={CATALOG_TABS.map((t) => t.label)}
                active={CATALOG_TABS.find((t) => t.value === catalog)?.label ?? ""}
                onSelect={(label) => {
                  setCatalog(CATALOG_TABS.find((t) => t.label === label)?.value ?? DEFAULT_CATALOG);
                  setSearch("");
                }}
              />
              <SearchInput
                placeholder="Search this catalog"
                className="ml-auto w-[260px]"
                value={search}
                onChange={(value) => setSearch(value)}
              />
            </>
          }
          head={head}
          footer={
            <div className="w-full">
              <Pager
                page={safePage}
                pageSize={pageSize}
                total={rows.length}
                onPageChange={setPage}
                noun="entries"
                busy={query.isFetching && !query.isPending}
              />
              <p className="t-caption mt-sp-3 text-ink-5">{CATALOG_SUBTITLE[catalog]}</p>
            </div>
          }
        >
          <TableBodySwap pageKey={`${catalog}-${safePage}`}>
            {query.isPending ? <TableSkeleton rows={pageSize} columns={cols} /> : null}

            {query.isError ? (
              <TableErrorRow columns={cols} error={query.error} onRetry={() => query.refetch()} />
            ) : null}

            {query.isSuccess && rows.length === 0 ? (
              <tr>
                <td colSpan={cols} className="h-[52px] border-b border-stroke-subtle px-sp-6">
                  <EmptyState
                    icon={Library}
                    title={search ? "No match in this catalog" : "This catalog is empty"}
                    description={
                      search
                        ? "No entry matches that term."
                        : "Nothing has been loaded into this reference table yet."
                    }
                  />
                </td>
              </tr>
            ) : null}

            {query.isSuccess && rows.length > 0 && catalog === "errors"
              ? (pageRows as ErrorEntry[]).map((r) => (
                  <tr
                    key={r.code}
                    className="group/row transition-colors duration-[120ms] hover:bg-surface-3"
                  >
                    <Td>
                      <span className="t-mono text-ink-1">{r.code}</span>
                    </Td>
                    <Td>
                      {r.domain ? (
                        <Token>{r.domain}</Token>
                      ) : (
                        <span className="t-caption text-ink-5">{"\u2014"}</span>
                      )}
                    </Td>
                    <Td>
                      <span className="t-ui text-ink-2">{orDash(r.message_fr)}</span>
                    </Td>
                    <Td>
                      <span className="t-ui text-ink-2" dir="rtl">
                        {orDash(r.message_ar)}
                      </span>
                    </Td>
                    <Td>
                      <span className="t-ui text-ink-2">{orDash(r.message_en)}</span>
                    </Td>
                  </tr>
                ))
              : null}

            {query.isSuccess && rows.length > 0 && catalog === "products"
              ? (pageRows as ProductEntry[]).map((r) => (
                  <tr
                    key={r.product_code}
                    className="group/row transition-colors duration-[120ms] hover:bg-surface-3"
                  >
                    <Td>
                      <span className="t-mono text-ink-1">{r.product_code}</span>
                    </Td>
                    <Td>
                      <span className="t-ui text-ink-1">{r.name}</span>
                    </Td>
                    <Td>
                      <Token>{r.plan_type}</Token>
                    </Td>
                    <Td>
                      <StatusChip status={activeStatusKey(r.active)} />
                    </Td>
                    <Td align="right">
                      {canEdit ? <CatalogRowActions catalog="products" product={r} /> : null}
                    </Td>
                  </tr>
                ))
              : null}

            {query.isSuccess && rows.length > 0 && catalog === "recharges"
              ? (pageRows as RechargeEntry[]).map((r) => (
                  <tr
                    key={r.code}
                    className="transition-colors duration-[120ms] hover:bg-surface-3"
                  >
                    <Td>
                      <span className="t-mono text-ink-1">{r.code}</span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono-l text-ink-1">{formatAmount(r.amount)}</span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {r.bonus_amount > 0 ? formatAmount(r.bonus_amount) : "\u2014"}
                      </span>
                    </Td>
                  </tr>
                ))
              : null}

            {query.isSuccess && rows.length > 0 && catalog === "areas"
              ? (pageRows as AreaEntry[]).map((r) => (
                  <tr
                    key={r.area_code}
                    className="group/row transition-colors duration-[120ms] hover:bg-surface-3"
                  >
                    <Td>
                      <span className="t-mono text-ink-1">{r.area_code}</span>
                    </Td>
                    <Td>
                      <span className="t-ui block truncate text-ink-1">{r.name_fr}</span>
                      {r.name_ar ? (
                        <span className="t-caption block truncate text-ink-4" dir="rtl">
                          {r.name_ar}
                        </span>
                      ) : null}
                    </Td>
                    <Td>
                      <Token>{areaTypeLabel(r.area_type)}</Token>
                    </Td>
                    <Td>
                      {r.parent_code ? (
                        <span className="t-mono text-ink-3">{r.parent_code}</span>
                      ) : (
                        <span className="t-caption text-ink-5">{"\u2014"}</span>
                      )}
                    </Td>
                    <Td>
                      <StatusChip status={activeStatusKey(r.active)} />
                    </Td>
                    <Td align="right">
                      {canEdit ? <CatalogRowActions catalog="areas" area={r} /> : null}
                    </Td>
                  </tr>
                ))
              : null}
          </TableBodySwap>
        </TableShell>
      </PageSection>

      {/* Incidents live on this page because they are a property of the geo referential above:
       * an outage can only name an area that exists here, and the agent reaches both through
       * the same lookup. */}
      <PageSection index={1}>
        <SectionHeading
          title="Network state"
          hint="Declared incidents the agent reports to callers"
          icon={RadioTower}
        />
        <OutageManager canEdit={canEdit} />
      </PageSection>
    </>
  );
}
