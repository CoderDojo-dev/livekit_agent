import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Users } from "lucide-react";
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
import { HeroStat, StatCard } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { CustomerDetail } from "@/components/nexus/customer-detail";
import { listCustomers, type CustomerRow } from "@/lib/api/customers.server";
import { getSystemOverview } from "@/lib/api/analytics.server";
import { customerKeys, analyticsKeys } from "@/lib/nexus/query-keys";
import {
  customerStatusKey,
  hasNext,
  hasPrevious,
  languageLabel,
  pageRange,
} from "@/lib/nexus/customer-view";
import { formatInteger, initials, maskPhone } from "@/lib/nexus/format";
import { useDebounced } from "@/hooks/use-debounced";

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Suspended", value: "suspended" },
  { label: "Closed", value: "closed" },
] as const;

export const Route = createFileRoute("/customers")({
  head: () => ({
    meta: [
      { title: "Customers \u2014 Nexus" },
      {
        name: "description",
        content:
          "The CRM registry: identity, subscriptions, open invoices and tickets per customer.",
      },
      { property: "og:title", content: "Customers \u2014 Nexus" },
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
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CustomerRow | null>(null);

  const debouncedSearch = useDebounced(search, 300);

  const list = useQuery({
    queryKey: customerKeys.list(debouncedSearch, status, PAGE_SIZE, offset),
    queryFn: () =>
      listCustomers({
        data: { search: debouncedSearch, status, limit: PAGE_SIZE, offset },
      }),
    placeholderData: keepPreviousData,
  });

  const overview = useQuery({
    queryKey: analyticsKeys.system(),
    queryFn: () => getSystemOverview(),
  });

  const rows = list.data?.customers ?? [];
  const total = list.data?.total ?? 0;
  const range = pageRange(offset, PAGE_SIZE, total);

  const filtering = debouncedSearch !== "" || status !== "";

  function changeSearch(value: string) {
    setSearch(value);
    setOffset(0);
  }

  function changeStatus(value: string) {
    setStatus(value);
    setOffset(0);
  }

  return (
    <>
      <PageSection className="grid gap-sp-6 xl:grid-cols-3">
        <HeroStat
          label="Customers"
          value={overview.data ? formatInteger(overview.data.metrics.total_customers) : "\u2014"}
          context="Identity records in crm.customers"
        />
        <StatCard
          label={filtering ? "Matching" : "Listed"}
          value={list.data ? formatInteger(total) : "\u2014"}
          context={filtering ? "Rows matching the current filters" : "All customers"}
        />
        <StatCard
          label="Page"
          value={total === 0 ? "0" : `${range.from}\u2013${range.to}`}
          context={`${PAGE_SIZE} per page`}
        />
      </PageSection>

      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput
                placeholder="Search name, email or phone"
                className="w-[280px]"
                value={search}
                onChange={(value) => changeSearch(value)}
              />
              <Segmented
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
            <>
              <span className="t-caption text-ink-4">
                {total === 0
                  ? "No customers"
                  : `Showing ${range.from}\u2013${range.to} of ${formatInteger(total)}`}
              </span>
              <div className="flex gap-sp-4">
                <Button
                  size="sm"
                  disabled={!hasPrevious(offset) || list.isPending}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  disabled={!hasNext(offset, PAGE_SIZE, total) || list.isPending}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </>
          }
        >
          {list.isPending ? (
            <TableSkeleton rows={8} columns={5} />
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
                    {c.contact_number ? maskPhone(c.contact_number) : "\u2014"}
                  </span>
                </Td>
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>

      <CustomerDetail customer={selected} onClose={() => setSelected(null)} />
    </>
  );
}
