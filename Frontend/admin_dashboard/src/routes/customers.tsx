import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { IdCard, Layers, Users } from "lucide-react";
import {
  Avatar,
  Button,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { HeroStat, StatCard, ShareBar } from "@/components/nexus/blocks";
import { Card, CardHeader } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, offsetFor, rangeFor } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";
import { CustomerDetail } from "@/components/nexus/customer-detail";
import { listCustomers, type CustomerRow } from "@/lib/api/customers.server";
import { getSystemOverview } from "@/lib/api/analytics.server";
import { getCustomerMix } from "@/lib/api/customer-mix.server";
import { customerKeys, analyticsKeys } from "@/lib/nexus/query-keys";
import { customerStatusKey, languageLabel } from "@/lib/nexus/customer-view";
import { formatInteger, initials, formatPhone } from "@/lib/nexus/format";
import { useDebounced } from "@/hooks/use-debounced";

const STATUS_OPTIONS = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Suspended", value: "suspended" },
  { label: "Closed", value: "closed" },
] as const;

export const Route = createFileRoute("/customers")({
  head: () => ({
    meta: [
      { title: pageTitle("Customers") },
      {
        name: "description",
        content:
          "The CRM registry: identity, subscriptions, open invoices and tickets per customer.",
      },
      { property: "og:title", content: pageTitle("Customers") },
      {
        property: "og:description",
        content: "Look up a customer and open their full 360 record.",
      },
    ],
  }),
  component: CustomersPage,
});

function CustomersPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string>("");
  const [page, setPage] = useState(0);

  /* 25 rows was a fixed guess that overflowed a laptop and wasted a large display. Customer rows
   * are single-line, so more of them fit than on the stacked tables. */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 500,
    min: 6,
    max: 16,
    fallback: 10,
  });
  const [selected, setSelected] = useState<CustomerRow | null>(null);

  const debouncedSearch = useDebounced(search, 300);

  const list = useQuery({
    queryKey: customerKeys.list(debouncedSearch, status, pageSize, offsetFor(page, pageSize)),
    queryFn: () =>
      listCustomers({
        data: {
          search: debouncedSearch,
          status,
          limit: pageSize,
          offset: offsetFor(page, pageSize),
        },
      }),
    placeholderData: keepPreviousData,
  });

  const overview = useQuery({
    queryKey: analyticsKeys.system(),
    queryFn: () => getSystemOverview(),
  });

  /* Real per-status totals (see customer-mix.server.ts) — the list endpoint carries no
   * breakdown, and inventing one from the current page would describe 10 rows as if it
   * described the estate. */
  const mix = useQuery({
    queryKey: customerKeys.mix(),
    queryFn: () => getCustomerMix(),
    staleTime: 60_000,
  });

  const rows = list.data?.customers ?? [];
  const total = list.data?.total ?? 0;
  useEffect(() => setPage(0), [debouncedSearch, status, pageSize]);
  const safePage = clampPage(page, total, pageSize);
  const range = rangeFor(safePage, pageSize, total);

  const filtering = debouncedSearch !== "" || status !== "";

  function changeSearch(value: string) {
    setSearch(value);
    setPage(0);
  }

  function changeStatus(value: string) {
    setStatus(value);
    setPage(0);
  }

  return (
    <>
      <PageSection index={0} className="grid gap-sp-6 xl:grid-cols-[1fr_1fr_1.3fr]">
        <HeroStat
          label="Customers"
          value={overview.data ? formatInteger(overview.data.metrics.total_customers) : "\u2014"}
          context="Identity records in crm.customers"
          icon={Users}
          /* The sparkline slot stays empty here on purpose: no customer time series exists on the
           * wire, and drawing one from session volume would label the wrong data as growth. The
           * distribution card to the right fills the band with something that IS true. */
        />
        <StatCard
          label={filtering ? "Matching" : "Listed"}
          value={list.data ? formatInteger(total) : "\u2014"}
          context={filtering ? "Rows matching the current filters" : "All customers"}
          meta={
            total === 0
              ? `${pageSize} per page`
              : `Showing ${range.from}\u2013${range.to} \u00b7 ${pageSize} per page`
          }
          icon={IdCard}
        />

        {/* Replaces a "Page 1\u201310" card that restated the footer. Real per-status totals. */}
        <Card className="flex flex-col">
          <CardHeader title="Status mix" subtitle="Across every customer record." icon={Layers} />
          <div className="mt-sp-7 flex-1">
            {mix.isPending ? (
              <div className="space-y-sp-5" role="status">
                <span className="sr-only">Loading status mix</span>
                <span className="shimmer block h-[10px] rounded-r-1" />
                <span className="shimmer block h-[10px] w-[60%] rounded-r-1" />
              </div>
            ) : (
              (() => {
                // null = not readable. Omitted entirely rather than drawn as a zero segment.
                const parts = [
                  { label: "Active", value: mix.data?.active ?? null },
                  { label: "Suspended", value: mix.data?.suspended ?? null, strong: true },
                  { label: "Closed", value: mix.data?.closed ?? null },
                ].filter(
                  (part): part is { label: string; value: number; strong?: boolean } =>
                    part.value !== null,
                );

                if (parts.length === 0) {
                  return (
                    <p className="t-caption text-ink-5">
                      The status breakdown could not be read just now.
                    </p>
                  );
                }

                return (
                  <ShareBar
                    parts={parts}
                    total={parts.reduce((sum, part) => sum + part.value, 0)}
                  />
                );
              })()
            )}
          </div>
        </Card>
      </PageSection>

      <PageSection index={1}>
        <TableShell
          minWidth={860}
          bodyAsChild
          busy={list.isFetching && !list.isPending}
          toolbar={
            <>
              <SearchInput
                placeholder="Search name, email or phone"
                className="w-[280px]"
                value={search}
                onChange={(value) => changeSearch(value)}
              />
              <Segmented
                groupId="customer-status"
                items={STATUS_OPTIONS.map((o) => o.label)}
                active={STATUS_OPTIONS.find((o) => o.value === status)?.label ?? "All"}
                onSelect={(label) =>
                  changeStatus(STATUS_OPTIONS.find((o) => o.label === label)?.value ?? "")
                }
              />
            </>
          }
          head={
            <tr>
              <Th>Customer</Th>
              <Th>Status</Th>
              <Th>Language</Th>
              <Th>Segment</Th>
              <Th align="right">Phone</Th>
            </tr>
          }
          footer={
            /* Was a bare Previous/Next pair with no sense of position in the set. The shared
             * Pager keeps the honest range readout and adds numbered jumps. */
            <Pager
              page={safePage}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              noun="customers"
              busy={list.isFetching && !list.isPending}
              className="w-full"
            />
          }
        >
          <TableBodySwap pageKey={`${safePage}-${status}-${debouncedSearch}`}>
            {list.isPending ? (
              <TableSkeleton rows={pageSize} columns={5} />
            ) : list.isError ? (
              <TableErrorRow columns={5} error={list.error} onRetry={() => list.refetch()} />
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="h-[52px] border-b border-stroke-subtle px-sp-6">
                  <EmptyState
                    icon={Users}
                    title={filtering ? "No matching customers" : "No customers yet"}
                    description={
                      filtering
                        ? "Adjust the search term or status filter."
                        : "The CRM registry is empty."
                    }
                  />
                </td>
              </tr>
            ) : (
              rows.map((c) => (
                <tr
                  key={c.customer_id}
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    if (
                      event.target !== event.currentTarget &&
                      (event.target as HTMLElement).closest(
                        "a, button, input, select, textarea, [role='button']",
                      )
                    ) {
                      return;
                    }

                    setSelected(c);
                  }}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;

                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelected(c);
                    }
                  }}
                  className="cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-n-12"
                >
                  <Td>
                    <span className="flex items-center gap-sp-5">
                      <Avatar initials={initials(c.name)} name={c.name} />
                      <span className="min-w-0">
                        <span className="t-ui block truncate text-ink-1">
                          {c.name}
                          {c.vip ? " " : ""}
                          {c.vip ? <Token strong>VIP</Token> : null}
                        </span>
                        <span className="t-caption block truncate text-ink-4">
                          {c.email ?? "\u2014"}
                        </span>
                      </span>
                    </span>
                  </Td>
                  <Td>
                    <StatusChip status={customerStatusKey(c.status) ?? ""} />
                  </Td>
                  <Td>
                    <Token mono={false}>{languageLabel(c.preferred_language)}</Token>
                  </Td>
                  <Td>
                    <span className="t-caption text-ink-4">{c.segment ?? "\u2014"}</span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">
                      {c.contact_number ? formatPhone(c.contact_number) : "\u2014"}
                    </span>
                  </Td>
                </tr>
              ))
            )}
          </TableBodySwap>
        </TableShell>
      </PageSection>

      <CustomerDetail customer={selected} onClose={() => setSelected(null)} />
    </>
  );
}
