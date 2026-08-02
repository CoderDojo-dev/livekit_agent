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
import { POLICIES } from "@/lib/nexus/data";

export const Route = createFileRoute("/policies")({
  head: () => ({
    meta: [
      { title: "Policies — Nexus" },
      {
        name: "description",
        content: "Versioned operating limits the agent and advisors must respect.",
      },
      { property: "og:title", content: "Policies — Nexus" },
      { property: "og:description", content: "Thresholds, versions and enforcement state." },
    ],
  }),
  component: PoliciesPage,
});

function PoliciesPage() {
  return (
    <PageSection>
      <TableShell
        toolbar={
          <>
            <SearchInput placeholder="Search policies" className="w-[260px]" />
            <Button icon={Plus} size="sm" variant="primary" className="ml-auto">
              New policy
            </Button>
          </>
        }
        head={
          <tr>
            <Th>Policy</Th>
            <Th align="right">Threshold</Th>
            <Th align="right">Version</Th>
            <Th>Status</Th>
          </tr>
        }
        footer={<span className="t-caption text-ink-4">{POLICIES.length} policies</span>}
      >
        {POLICIES.map((p) => (
          <tr key={p.name} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="t-ui text-ink-1">{p.name}</span>
            </Td>
            <Td align="right">
              <Token>{p.threshold}</Token>
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{p.version}</span>
            </Td>
            <Td>
              <StatusChip status={p.status} />
            </Td>
          </tr>
        ))}
      </TableShell>
    </PageSection>
  );
}
