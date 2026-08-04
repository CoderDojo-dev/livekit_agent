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
      { title: "Reference \u2014 Nexus" },
      {
        name: "description",
        content:
          "Admin-managed catalogs the agent reads at runtime: errors, plans, recharges, zones.",
      },
      { property: "og:title", content: "Reference \u2014 Nexus" },
      {
        property: "og:description",
        content: "Error messages, plans, recharges and geo areas.",
      },
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
              items={CATALOG_TABS.map((t) => t.label)}
              active={CATALOG_TABS.find((t) => t.value === catalog)?.label ?? ""}
              onSelect={(label) => {
                setCatalog(CATALOG_TABS.find((t) => t.label === label)?.value ?? "errors");
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
        footer={<span className="t-caption text-ink-4">{CATALOG_SUBTITLE[catalog]}</span>}
      >
        {query.isPending ? <TableSkeleton rows={8} columns={cols} /> : null}

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
          ? (rows as ErrorEntry[]).map((r) => (
              <tr key={r.code} className="transition-colors duration-[120ms] hover:bg-surface-3">
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
          ? (rows as ProductEntry[]).map((r) => (
              <tr
                key={r.product_code}
                className="transition-colors duration-[120ms] hover:bg-surface-3"
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
              </tr>
            ))
          : null}

        {query.isSuccess && rows.length > 0 && catalog === "recharges"
          ? (rows as RechargeEntry[]).map((r) => (
              <tr key={r.code} className="transition-colors duration-[120ms] hover:bg-surface-3">
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
          ? (rows as AreaEntry[]).map((r) => (
              <tr
                key={r.area_code}
                className="transition-colors duration-[120ms] hover:bg-surface-3"
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
              </tr>
            ))
          : null}
      </TableShell>
    </PageSection>
  );
}
