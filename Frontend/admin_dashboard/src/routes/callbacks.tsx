import { createFileRoute } from "@tanstack/react-router";
import { Avatar, StatusChip, TableShell, Td, Th, Token } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CALLBACKS } from "@/lib/nexus/data";
import { maskPhone } from "@/lib/nexus/format";

export const Route = createFileRoute("/callbacks")({
  head: () => ({
    meta: [
      { title: "Callbacks — Nexus" },
      { name: "description", content: "Scheduled return calls, their windows and assigned advisors." },
      { property: "og:title", content: "Callbacks — Nexus" },
      { property: "og:description", content: "Queued and pending callback requests." },
    ],
  }),
  component: CallbacksPage,
});

function CallbacksPage() {
  return (
    <PageSection>
      <TableShell
        head={
          <tr>
            <Th>Customer</Th>
            <Th>Window</Th>
            <Th>Advisor</Th>
            <Th>Status</Th>
          </tr>
        }
        footer={<span className="t-caption text-ink-4">{CALLBACKS.length} callbacks scheduled</span>}
      >
        {CALLBACKS.map((c) => (
          <tr key={c.name} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="t-ui block text-ink-1">{c.name}</span>
              <span className="t-mono-s block text-ink-4">{maskPhone(c.phone)}</span>
            </Td>
            <Td>
              <Token>{c.window}</Token>
            </Td>
            <Td>
              {c.advisor ? (
                <Avatar initials={c.advisor} size="sm" name={c.advisor} />
              ) : (
                <span className="t-caption text-ink-5">Unassigned</span>
              )}
            </Td>
            <Td>
              <StatusChip status={c.status} />
            </Td>
          </tr>
        ))}
      </TableShell>
    </PageSection>
  );
}
