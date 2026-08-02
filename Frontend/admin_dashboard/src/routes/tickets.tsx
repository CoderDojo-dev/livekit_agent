import { createFileRoute } from "@tanstack/react-router";
import { Plus, Filter } from "lucide-react";
import {
  Avatar,
  Button,
  PriorityMeter,
  SearchInput,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { StatCard, StatGrid } from "@/components/nexus/blocks";
import { PageSection } from "@/components/nexus/app-topbar";
import { TICKETS, TICKET_STATS } from "@/lib/nexus/data";

export const Route = createFileRoute("/tickets")({
  head: () => ({
    meta: [
      { title: "Ticket Management — Nexus" },
      {
        name: "description",
        content: "Track, assign and resolve every support request with priority and status at a glance.",
      },
      { property: "og:title", content: "Ticket Management — Nexus" },
      { property: "og:description", content: "Open, in-progress, resolved and closed tickets." },
    ],
  }),
  component: TicketsPage,
});

function TicketsPage() {
  return (
    <>
      <PageSection>
        <StatGrid>
          {TICKET_STATS.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </StatGrid>
      </PageSection>

      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput placeholder="Search tickets" className="w-[260px]" />
              <Button icon={Filter} size="sm">
                Filters
              </Button>
              <Button icon={Plus} size="sm" variant="primary" className="ml-auto">
                New ticket
              </Button>
            </>
          }
          head={
            <tr>
              <Th>Ticket</Th>
              <Th>Customer</Th>
              <Th>Priority</Th>
              <Th>Status</Th>
              <Th>Advisor</Th>
              <Th align="right">Updated</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">Showing {TICKETS.length} of 205 tickets</span>
              <div className="flex gap-sp-4">
                <Button size="sm">Previous</Button>
                <Button size="sm">Next</Button>
              </div>
            </>
          }
        >
          {TICKETS.map((t) => (
            <tr key={t.id} className="transition-colors duration-[120ms] hover:bg-surface-3">
              <Td>
                <span className="flex items-center gap-sp-5">
                  <Token>{t.id}</Token>
                  <span className="t-ui truncate text-ink-1">{t.subject}</span>
                </span>
              </Td>
              <Td>{t.customer}</Td>
              <Td>
                <PriorityMeter priority={t.priority} />
              </Td>
              <Td>
                <StatusChip status={t.status} />
              </Td>
              <Td>
                {t.advisor ? (
                  <Avatar initials={t.advisor} size="sm" name={t.advisor} />
                ) : (
                  <span className="t-caption text-ink-5">Unassigned</span>
                )}
              </Td>
              <Td align="right">
                <span className="t-mono text-ink-3">{t.updated}</span>
              </Td>
            </tr>
          ))}
        </TableShell>
      </PageSection>
    </>
  );
}
