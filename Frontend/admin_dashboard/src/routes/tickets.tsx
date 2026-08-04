import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { TicketX } from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  PriorityMeter,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import { listTickets } from "@/lib/api/tickets.server";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  categoryLabel,
  statusCount,
  ticketCustomer,
  ticketPriorityLevel,
  ticketStatusKey,
  ticketSubject,
  ticketTime,
} from "@/lib/nexus/ticket-view";
import { availabilityKeys, ticketKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";

const COLUMN_COUNT = 6;

const CATEGORY_OPTIONS = [
  { id: "", label: "All" },
  { id: "network_complaint", label: "Network" },
  { id: "formal_complaint", label: "Complaint" },
  { id: "technical", label: "Technical" },
  { id: "billing", label: "Billing" },
  { id: "other", label: "Other" },
];

export const Route = createFileRoute("/tickets")({
  head: () => ({
    meta: [
      { title: "Ticket Management — Nexus" },
      {
        name: "description",
        content: "Support tickets mirrored from GLPI, with status, priority and sync freshness.",
      },
      { property: "og:title", content: "Ticket Management — Nexus" },
      { property: "og:description", content: "Open, in-progress, resolved and closed tickets." },
    ],
  }),
  component: TicketsPage,
});

function TicketsPage() {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);

  const ticketsQuery = useQuery({
    queryKey: ticketKeys.list(status, category, "", search, limit),
    queryFn: () =>
      listTickets({
        data: {
          limit,
          offset: 0,
          status: status || undefined,
          category: category || undefined,
          search: search || undefined,
        },
      }),
  });

  // F14 — business timezone; shared cache with /availability, /callbacks and /calls.
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const rows = ticketsQuery.data?.tickets ?? [];
  const total = ticketsQuery.data?.total ?? 0;
  const counts = ticketsQuery.data?.counts;

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection>
        <Card>
          <div className="grid grid-cols-2 gap-sp-6 md:grid-cols-5">
            {STATUS_ORDER.map((key) => {
              const active = status === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStatus(active ? "" : key)}
                  className="text-left"
                  aria-pressed={active}
                >
                  <span className="t-micro block text-ink-5">{STATUS_LABELS[key]}</span>
                  <span
                    className={
                      active ? "t-metric-m block text-ink-1" : "t-metric-m block text-ink-3"
                    }
                  >
                    {formatInteger(statusCount(counts, key))}
                  </span>
                </button>
              );
            })}
          </div>
          {/* F2 — never let this read as "all GLPI tickets". */}
          <p className="t-caption mt-sp-6 text-ink-5">
            Mirrored from GLPI. Tickets raised outside this platform appear once a caller asks about
            them.
            {!timeZone && !coverageQuery.isPending
              ? " Times shown in UTC — the business timezone could not be loaded."
              : null}
          </p>
        </Card>
      </PageSection>

      {/* ---------- Table ---------- */}
      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput
                placeholder="Search subject or ID"
                className="w-[260px]"
                value={search}
                onChange={setSearch}
              />
              <Segmented
                items={CATEGORY_OPTIONS.map((o) => o.label)}
                active={CATEGORY_OPTIONS.find((o) => o.id === category)?.label ?? "All"}
                onSelect={(label) =>
                  setCategory(CATEGORY_OPTIONS.find((o) => o.label === label)?.id ?? "")
                }
              />
            </>
          }
          head={
            <tr>
              <Th>Ticket</Th>
              <Th>Customer</Th>
              <Th>Category</Th>
              <Th>Priority</Th>
              <Th>Status</Th>
              {/* F8 — "Synced", not "Updated": last_synced_at is when we last agreed with GLPI. */}
              <Th align="right">Synced</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                Showing {rows.length} of {formatInteger(total)} tickets
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </>
          }
        >
          {ticketsQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={6} />
          ) : ticketsQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={ticketsQuery.error}
              onRetry={() => ticketsQuery.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={TicketX}
                  title="No tickets found"
                  description="No mirrored ticket matches this filter."
                />
              </td>
            </tr>
          ) : (
            rows.map((t) => {
              const priority = ticketPriorityLevel(t.priority);
              return (
                <tr
                  key={t.ticket_id}
                  className="transition-colors duration-[120ms] hover:bg-surface-3"
                >
                  <Td>
                    <span className="flex items-center gap-sp-5">
                      {/* F13 — the GLPI id, never the internal UUID. */}
                      <Token>{t.ticket_id}</Token>
                      <span className="t-ui truncate text-ink-1">{ticketSubject(t.subject)}</span>
                    </span>
                  </Td>
                  <Td>
                    <span className="flex items-center gap-sp-4">
                      <span className="truncate">{ticketCustomer(t.customer_name)}</span>
                      {t.customer_vip ? <Token strong>VIP</Token> : null}
                    </span>
                  </Td>
                  <Td>
                    <Token mono={false}>{categoryLabel(t.category)}</Token>
                  </Td>
                  <Td>
                    {/* F6 — named priorities map honestly; NULL (untriaged) renders a muted dash. */}
                    {priority ? (
                      <PriorityMeter priority={priority} />
                    ) : (
                      <span className="t-caption text-ink-5">—</span>
                    )}
                  </Td>
                  <Td>
                    <StatusChip status={ticketStatusKey(t.status)} />
                  </Td>
                  <Td align="right">
                    <span className="t-mono text-ink-3">
                      {ticketTime(t.last_synced_at, timeZone)}
                    </span>
                  </Td>
                </tr>
              );
            })
          )}
        </TableShell>
      </PageSection>
    </>
  );
}
