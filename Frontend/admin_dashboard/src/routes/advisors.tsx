import { createFileRoute } from "@tanstack/react-router";
import {
  Avatar,
  SearchInput,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { ADVISORS } from "@/lib/nexus/data";

export const Route = createFileRoute("/advisors")({
  head: () => ({
    meta: [
      { title: "Advisors — Nexus" },
      {
        name: "description",
        content: "Advisor presence, live queue depth and volume handled today.",
      },
      { property: "og:title", content: "Advisors — Nexus" },
      { property: "og:description", content: "Who is online, on call and away." },
    ],
  }),
  component: AdvisorsPage,
});

function AdvisorsPage() {
  return (
    <PageSection>
      <TableShell
        toolbar={<SearchInput placeholder="Search advisors" className="w-[260px]" />}
        head={
          <tr>
            <Th>Advisor</Th>
            <Th>Role</Th>
            <Th align="right">Queue</Th>
            <Th align="right">Handled</Th>
            <Th>Status</Th>
          </tr>
        }
        footer={<span className="t-caption text-ink-4">{ADVISORS.length} advisors</span>}
      >
        {ADVISORS.map((a) => (
          <tr key={a.name} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="flex items-center gap-sp-5">
                <Avatar initials={a.initials} name={a.name} />
                <span className="t-ui text-ink-1">{a.name}</span>
              </span>
            </Td>
            <Td>
              <Token mono={false}>{a.role}</Token>
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{a.queue}</span>
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{a.handled}</span>
            </Td>
            <Td>
              <StatusChip status={a.status} />
            </Td>
          </tr>
        ))}
      </TableShell>
    </PageSection>
  );
}
