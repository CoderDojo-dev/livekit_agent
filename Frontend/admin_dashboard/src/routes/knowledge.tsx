import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FileQuestion, Search } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { InlineError, TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { KnowledgeUpload } from "@/components/nexus/knowledge-upload";
import { KnowledgePurge } from "@/components/nexus/knowledge-purge";
import { RetrievalProbe } from "@/components/nexus/retrieval-probe";
import { knowledgeHealth, listDocuments } from "@/lib/api/knowledge.server";
import { knowledgeKeys } from "@/lib/nexus/query-keys";
import {
  archivedCount,
  documentStatusKey,
  documentTypeLabel,
  healthSummary,
  languageLabel,
  visibleDocuments,
} from "@/lib/nexus/knowledge-view";
import { Route as RootRoute } from "@/routes/__root";
import { hasRank } from "@/lib/api/session";
import { formatInteger } from "@/lib/nexus/format";
import type { Outcome } from "@/components/nexus/knowledge-upload";

const COLUMN_COUNT = 7;

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
  const { session } = RootRoute.useRouteContext();
  const isAdmin = session !== null && hasRank(session, "administrateur");

  const [search, setSearch] = useState("");
  const [hideArchived, setHideArchived] = useState(true);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  // F10 — a 503 on the list renders as an error state, never an empty table.
  const documentsQuery = useQuery({
    queryKey: knowledgeKeys.documents(),
    queryFn: () => listDocuments(),
  });

  // F11 — readiness probe; ce_gate may legitimately be "warming" and must not read as degraded.
  const healthQuery = useQuery({
    queryKey: knowledgeKeys.health(),
    queryFn: () => knowledgeHealth(),
  });

  const docs = useMemo(() => documentsQuery.data?.documents ?? [], [documentsQuery.data]);
  const totalDocs = documentsQuery.data?.total_documents ?? 0;
  const totalChunks = documentsQuery.data?.total_chunks ?? 0;

  // F12 — preserve the server's ordering (source ASC, version DESC); never client-side re-sort.
  const visible = useMemo(() => visibleDocuments(docs, hideArchived), [docs, hideArchived]);

  const filtered = useMemo(() => {
    if (!search.trim()) return visible;
    const needle = search.toLowerCase();
    return visible.filter(
      (d) => d.source.toLowerCase().includes(needle) || d.title.toLowerCase().includes(needle),
    );
  }, [visible, search]);

  const hiddenArchived = archivedCount(docs);
  const health = healthQuery.data ? healthSummary(healthQuery.data) : null;

  return (
    <>
      {/* ---------- 1. Index health strip (F11) ---------- */}
      <PageSection>
        <Card>
          {healthQuery.isPending ? (
            <div className="flex flex-col gap-sp-3" role="status">
              <span className="sr-only">Loading index health</span>
              <span className="t-micro text-ink-5">Status</span>
              <span className="t-metric-m text-ink-3">Checking…</span>
            </div>
          ) : healthQuery.isError ? (
            <InlineError error={healthQuery.error} />
          ) : health && health.ready ? (
            <div className="grid grid-cols-2 gap-sp-6 md:grid-cols-5">
              <HealthValue label="Status" value="Searchable" />
              <HealthValue label="Model" value={healthQuery.data?.model ?? "—"} mono />
              <HealthValue
                label="Dimensions"
                value={String(healthQuery.data?.dimensions ?? "—")}
                mono
              />
              <HealthValue
                label="Points"
                value={formatInteger(healthQuery.data?.points ?? 0)}
                mono
              />
              <HealthValue label="Collection" value={healthQuery.data?.collection ?? "—"} mono />
            </div>
          ) : health && !health.ready ? (
            <div>
              <p className="t-title-3 text-ink-1">Index degraded</p>
              <p className="t-caption mt-sp-2 text-ink-4">
                Failing checks: {health.failing.join(", ") || "unknown"}
              </p>
            </div>
          ) : null}
        </Card>
      </PageSection>

      {/* ---------- 2. Corpus inventory ---------- */}
      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput
                placeholder="Search sources"
                className="w-[260px]"
                value={search}
                onChange={setSearch}
              />
              <Segmented
                items={["Hide archived", "Show archived"]}
                active={hideArchived ? "Hide archived" : "Show archived"}
                onSelect={(label) => setHideArchived(label === "Hide archived")}
              />
              {isAdmin ? <KnowledgeUpload onOutcome={setOutcome} /> : null}
            </>
          }
          head={
            <tr>
              <Th>Source</Th>
              <Th>Type</Th>
              <Th>Lang</Th>
              <Th align="right">Chunks</Th>
              {/* F5 — Version replaces the mock's "Updated": no timestamp on the wire. */}
              <Th align="right">Version</Th>
              <Th>Status</Th>
              {isAdmin ? <Th align="right" /> : null}
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                {/* F13 — use the server totals, not client-side arithmetic. */}
                {formatInteger(totalDocs)} documents · {formatInteger(totalChunks)} chunks indexed
                {hideArchived && hiddenArchived > 0
                  ? ` · (${hiddenArchived} archived hidden)`
                  : null}
              </span>
              {outcome ? (
                <span
                  className={
                    outcome.tone === "success"
                      ? "t-caption text-ink-2"
                      : outcome.tone === "neutral"
                        ? "t-caption text-ink-4"
                        : "t-caption text-ink-3"
                  }
                >
                  {outcome.message}
                </span>
              ) : null}
            </>
          }
        >
          {documentsQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={8} />
          ) : documentsQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={documentsQuery.error}
              onRetry={() => documentsQuery.refetch()}
            />
          ) : docs.length === 0 ? (
            // F10 — EmptyState ONLY on a 200 with zero documents.
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={FileQuestion}
                  title="No documents indexed"
                  description="Upload a source document to start building the corpus."
                />
              </td>
            </tr>
          ) : filtered.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={Search}
                  title="No matching sources"
                  description="No document matches this search."
                />
              </td>
            </tr>
          ) : (
            filtered.map((d) => (
              <tr
                key={d.document_id}
                className="transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <Td>
                  {/* F6 — source is the identity; title is decoration and often empty. */}
                  <span className="t-mono text-ink-1">{d.source}</span>
                  {d.title && d.title !== d.source ? (
                    <span className="t-caption mt-sp-1 block text-ink-4">{d.title}</span>
                  ) : null}
                </Td>
                <Td>
                  <Token mono={false}>{documentTypeLabel(d.document_type)}</Token>
                </Td>
                <Td>
                  <span className="t-caption text-ink-3">{languageLabel(d.language)}</span>
                </Td>
                <Td align="right">
                  <Token>{d.chunks}</Token>
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">v{d.version}</span>
                </Td>
                <Td>
                  {/* F3 — ready maps onto indexed; never render the raw status string. */}
                  <StatusChip status={documentStatusKey(d.status)} />
                </Td>
                {isAdmin ? (
                  <Td align="right">
                    <KnowledgePurge source={d.source} />
                  </Td>
                ) : null}
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>

      {/* ---------- 3. Retrieval probe (F16) ---------- */}
      <PageSection>
        <RetrievalProbe />
      </PageSection>
    </>
  );
}

function HealthValue({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <span className="t-micro block text-ink-5">{label}</span>
      <span
        className={
          mono ? "t-metric-m block truncate font-mono text-ink-1" : "t-metric-m block text-ink-1"
        }
      >
        {value}
      </span>
    </div>
  );
}
