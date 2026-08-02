import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import {
  Button,
  SearchInput,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { RULES } from "@/lib/nexus/data";

export const Route = createFileRoute("/rules")({
  head: () => ({
    meta: [
      { title: "Automation Rules — Nexus" },
      {
        name: "description",
        content: "Trigger and action pairs that route, escalate and close work automatically.",
      },
      { property: "og:title", content: "Automation Rules — Nexus" },
      { property: "og:description", content: "Triggers, actions and run counts." },
    ],
  }),
  component: RulesPage,
});

function RulesPage() {
  return (
    <PageSection>
      <TableShell
        toolbar={
          <>
            <SearchInput placeholder="Search rules" className="w-[260px]" />
            <Button icon={Plus} size="sm" variant="primary" className="ml-auto">
              New rule
            </Button>
          </>
        }
        head={
          <tr>
            <Th>Rule</Th>
            <Th>Trigger</Th>
            <Th>Action</Th>
            <Th align="right">Runs</Th>
            <Th>Status</Th>
          </tr>
        }
        footer={<span className="t-caption text-ink-4">{RULES.length} rules</span>}
      >
        {RULES.map((r) => (
          <tr key={r.name} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="t-ui text-ink-1">{r.name}</span>
            </Td>
            <Td>
              <Token>{r.trigger}</Token>
            </Td>
            <Td>
              <Token>{r.action}</Token>
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{r.runs}</span>
            </Td>
            <Td>
              <StatusChip status={r.status} />
            </Td>
          </tr>
        ))}
      </TableShell>
    </PageSection>
  );
}
