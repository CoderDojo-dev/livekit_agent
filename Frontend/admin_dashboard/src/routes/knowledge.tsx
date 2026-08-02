import { createFileRoute } from "@tanstack/react-router";
import { Upload } from "lucide-react";
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
import { KNOWLEDGE_SOURCES } from "@/lib/nexus/data";

export const Route = createFileRoute("/knowledge")({
  head: () => ({
    meta: [
      { title: "Knowledge Base — Nexus" },
      {
        name: "description",
        content: "Indexed documents, chunk counts and processing state for the agent's knowledge.",
      },
      { property: "og:title", content: "Knowledge Base — Nexus" },
      { property: "og:description", content: "Sources the AI agent retrieves answers from." },
    ],
  }),
  component: KnowledgePage,
});

function KnowledgePage() {
  return (
    <PageSection>
      <TableShell
        toolbar={
          <>
            <SearchInput placeholder="Search sources" className="w-[260px]" />
            <Button icon={Upload} size="sm" variant="primary" className="ml-auto">
              Upload source
            </Button>
          </>
        }
        head={
          <tr>
            <Th>Source</Th>
            <Th align="right">Chunks</Th>
            <Th align="right">Updated</Th>
            <Th>Status</Th>
          </tr>
        }
        footer={
          <span className="t-caption text-ink-4">
            {KNOWLEDGE_SOURCES.length} sources indexed
          </span>
        }
      >
        {KNOWLEDGE_SOURCES.map((s) => (
          <tr key={s.name} className="transition-colors duration-[120ms] hover:bg-surface-3">
            <Td>
              <span className="t-mono text-ink-1">{s.name}</span>
            </Td>
            <Td align="right">
              <Token>{s.chunks}</Token>
            </Td>
            <Td align="right">
              <span className="t-mono text-ink-3">{s.updated}</span>
            </Td>
            <Td>
              <StatusChip status={s.status} />
            </Td>
          </tr>
        ))}
      </TableShell>
    </PageSection>
  );
}
