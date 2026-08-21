import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { TicketX } from "lucide-react";
import {
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
import { CountStrip } from "@/components/nexus/count-strip";
import { NoteBanner } from "@/components/nexus/note-banner";
import { TicketNoteMarker, TicketUpdateButton } from "@/components/nexus/ticket-update";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
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
import { clampPage, offsetFor } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { pageTitle } from "@/lib/nexus/brand";

const COLUMN_COUNT = 7;

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
      { title: pageTitle("Ticket Management") },
      {
        name: "description",
        content: "Support tickets mirrored from GLPI, with status, priority and sync freshness.",
      },
      { property: "og:title", content: pageTitle("Ticket Management") },
      { property: "og:description", content: "Open, in-progress, resolved and closed tickets." },
    ],
  }),
  component: TicketsPage,
});

function TicketsPage() {
  /* Open tickets are the work; closed ones are history. The page opens on the work. */
  const [status, setStatus] = useState("open");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  /**
   * Rows per page are derived from the viewport rather than fixed.
   *
   * The old page rendered 50 rows and grew to 200 via "Load more" — roughly 10 600px, twelve
   * screens of repetitive records. Sizing to the viewport means the table always ends just below
   * the fold and the pager is the way through the set, whatever the display.
   */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 480,
    min: 5,
    max: 14,
    fallback: 8,
  });

  const ticketsQuery = useQuery({
    queryKey: ticketKeys.list(status, category, "", search, pageSize, offsetFor(page, pageSize)),
    queryFn: () =>
      listTickets({
        data: {
          limit: pageSize,
          offset: offsetFor(page, pageSize),
          status: status || undefined,
          category: category || undefined,
          search: search || undefined,
        },
      }),
    // Keeps the previous page on screen while the next one loads, so paging dissolves rather
    // than flashing an empty table. The progress sweep carries the "working" signal instead.
    placeholderData: keepPreviousData,
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

  /* Any filter change resets to the first page — otherwise a narrower result set strands the
   * reader on a page index that no longer exists and the table renders empty. */
  useEffect(() => setPage(0), [status, category, search, pageSize]);
  const safePage = clampPage(page, total, pageSize);

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection index={0}>
        <Card>
          <CountStrip
            items={STATUS_ORDER.map((key) => ({
              id: key,
              label: STATUS_LABELS[key] ?? key,
              value: statusCount(counts, key),
            }))}
            active={status}
            onSelect={(next) => setStatus(next)}
            loading={ticketsQuery.isPending}
          />
          {/* F2 — never let this read as "all GLPI tickets". */}
          <NoteBanner className="mt-sp-7">
            Mirrored from GLPI. Tickets raised elsewhere appear once a caller asks about them.
            {!timeZone && !coverageQuery.isPending ? " Times in UTC." : null}
          </NoteBanner>
        </Card>
      </PageSection>

      {/* ---------- Table ---------- */}
      <PageSection index={1}>
        <TableShell
          minWidth={860}
          bodyAsChild
          busy={ticketsQuery.isFetching && !ticketsQuery.isPending}
          toolbar={
            <>
              <SearchInput
                placeholder="Search subject or ID"
                className="w-full sm:w-[260px]"
                value={search}
                onChange={setSearch}
              />
              <Segmented
                groupId="ticket-category"
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
              {/* Actions. Unlabelled: the icon carries its own accessible name. */}
              <Th align="right" />
            </tr>
          }
          footer={
            <Pager
              page={safePage}
              pageSize={pageSize}
              total={total}
              onPageChange={setPage}
              noun="tickets"
              busy={ticketsQuery.isFetching && !ticketsQuery.isPending}
              className="w-full"
            />
          }
        >
          <TableBodySwap pageKey={`${safePage}-${status}-${category}`}>
            {ticketsQuery.isPending ? (
              <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
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
                    className="group/row transition-colors duration-[120ms] hover:bg-surface-3"
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
                      <span className="t-mono whitespace-nowrap text-ink-3">
                        {ticketTime(t.last_synced_at, timeZone)}
                      </span>
                    </Td>
                    <Td align="right">
                      {/* Revealed on row hover/focus so a table of 12 rows is not a wall of
                       * buttons, but always reachable by keyboard. */}
                      <span className="inline-flex opacity-0 transition-opacity duration-[120ms] group-hover/row:opacity-100 focus-within:opacity-100">
                        <TicketUpdateButton
                          ticketId={t.ticket_id}
                          currentStatus={t.status}
                          currentNote={t.admin_note}
                          subject={ticketSubject(t.subject)}
                        />
                      </span>
                    </Td>
                  </tr>
                );
              })
            )}
          </TableBodySwap>
        </TableShell>
      </PageSection>
    </>
  );
}
