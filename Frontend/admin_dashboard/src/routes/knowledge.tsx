import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpenCheck, FileQuestion, Search } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  PresenceDot,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { InlineError, TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
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
import { pageTitle } from "@/lib/nexus/brand";

const COLUMN_COUNT = 7;

export const Route = createFileRoute("/knowledge")({
  head: () => ({
    meta: [
      { title: pageTitle("Knowledge Base") },
      {
        name: "description",
        content: "Indexed documents, chunk counts and processing state for the agent's knowledge.",
      },
      { property: "og:title", content: pageTitle("Knowledge Base") },
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
  const [page, setPage] = useState(0);

  /* The corpus inventory rendered every indexed document at once. Paging keeps the page a
   * fixed height however large the corpus grows. */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.table,
    chrome: 620,
    min: 5,
    max: 12,
    fallback: 8,
  });

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

  useEffect(() => setPage(0), [search, hideArchived, pageSize]);
  const safePage = clampPage(page, filtered.length, pageSize);
  /* `visible` above already means "not archived" on this page; this is the paged window. */
  const pageRows = slicePage(filtered, safePage, pageSize);

  const hiddenArchived = archivedCount(docs);
  const health = healthQuery.data ? healthSummary(healthQuery.data) : null;

  return (
    <>
      {/* ---------- 1. Index health strip (F11) ---------- */}
      <PageSection index={0}>
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
            /*
             * Was five equal `t-metric-m` values in a row — "Searchable", a model id, a dimension
             * count, a point count and a collection name, all shouting at the same volume. Four
             * of those are machine facts nobody acts on; only one answers the question a person
             * actually arrives with, which is "can the agent answer from this right now?".
             *
             * So the answer leads, in plain language, and the machine detail becomes a quiet
             * mono strip beneath it.
             */
            <div className="flex flex-wrap items-center gap-x-sp-8 gap-y-sp-6">
              <div className="flex min-w-0 items-center gap-sp-6">
                <span className="inline-flex size-[40px] shrink-0 items-center justify-center rounded-r-3 border border-stroke-default bg-surface-3 text-ink-2">
                  <BookOpenCheck size={18} strokeWidth={1.5} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="t-title-3 flex items-center gap-sp-4 text-ink-1">
                    The agent can answer from this library
                    <PresenceDot live />
                  </p>
                  <p className="t-caption mt-sp-2 text-ink-4">
                    {formatInteger(healthQuery.data?.points ?? 0)} passages indexed and searchable
                    across {formatInteger(totalDocs)} documents.
                  </p>
                </div>
              </div>

              {/* The machine detail, demoted to where it belongs. */}
              <div className="ml-auto flex flex-wrap items-center gap-sp-4">
                <Token>{healthQuery.data?.model ?? "—"}</Token>
                <Token>{healthQuery.data?.dimensions ?? "—"}d</Token>
                <Token>{healthQuery.data?.collection ?? "—"}</Token>
              </div>
            </div>
          ) : health && !health.ready ? (
            <div className="flex items-center gap-sp-6">
              <span className="inline-flex size-[40px] shrink-0 items-center justify-center rounded-r-3 border border-stroke-strong bg-surface-3 text-ink-1">
                <AlertTriangle size={18} strokeWidth={1.5} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="t-title-3 text-ink-1">The agent cannot search this library</p>
                <p className="t-caption mt-sp-2 text-ink-4">
                  Answers will fall back to the model alone until this clears. Failing checks:{" "}
                  {health.failing.join(", ") || "unknown"}.
                </p>
              </div>
            </div>
          ) : null}
        </Card>
      </PageSection>

      {/* ---------- 2. Corpus inventory ---------- */}
      <PageSection index={1}>
        <TableShell
          minWidth={980}
          bodyAsChild
          busy={documentsQuery.isFetching && !documentsQuery.isPending}
          toolbar={
            <>
              <SearchInput
                placeholder="Search sources"
                className="w-[260px]"
                value={search}
                onChange={setSearch}
              />
              <Segmented
                groupId="knowledge-archive"
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
            <div className="w-full">
              <Pager
                page={safePage}
                pageSize={pageSize}
                total={filtered.length}
                onPageChange={setPage}
                noun="documents"
                busy={documentsQuery.isFetching && !documentsQuery.isPending}
              />
              <div className="mt-sp-3 flex flex-wrap items-center justify-between gap-sp-4">
                <span className="t-caption text-ink-5">
                  {/* F13 — use the server totals, not client-side arithmetic. The pager above
                   * counts the FILTERED set; this line reports the corpus as a whole. */}
                  {formatInteger(totalDocs)} documents · {formatInteger(totalChunks)} chunks indexed
                  {hideArchived && hiddenArchived > 0
                    ? ` · ${hiddenArchived} archived hidden`
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
              </div>
            </div>
          }
        >
          <TableBodySwap pageKey={`${safePage}-${hideArchived}`}>
            {documentsQuery.isPending ? (
              <TableSkeleton columns={COLUMN_COUNT} rows={pageSize} />
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
              pageRows.map((d) => (
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
          </TableBodySwap>
        </TableShell>
      </PageSection>

      {/* ---------- 3. Retrieval probe (F16) ---------- */}
      <PageSection index={2}>
        <RetrievalProbe />
      </PageSection>
    </>
  );
}
