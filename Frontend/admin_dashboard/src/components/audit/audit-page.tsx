import { useEffect, useState } from "react";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { Archive, Fingerprint, Link2, ScrollText, ShieldCheck } from "lucide-react";
import {
  Card,
  CardHeader,
  Button,
  StatusChip,
  Token,
  EmptyState,
  TableShell,
  Th,
  Td,
  SearchInput,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableSkeleton, InlineError, TableErrorRow } from "@/components/nexus/states";
import { CursorPager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import { RetentionPanel } from "@/components/nexus/retention-panel";
import { SectionHeading } from "@/components/nexus/blocks";
import { verifyAuditChain, runIntegrityReport, listAuditEntries } from "@/lib/api/audit.server";
import { auditKeys } from "@/lib/nexus/query-keys";
import {
  checkStatusKey,
  orphanLabel,
  totalOrphans,
  shortHash,
  eventLabel,
  formatInstant,
  isLinked,
} from "@/lib/nexus/audit-view";
import { formatInteger } from "@/lib/nexus/format";

export function AuditPage() {
  return (
    <>
      {/* Three bands, in the order an auditor works: prove it is intact, then act on what the
       * proof found, then read the record itself. Previously all three sat as unlabelled peers
       * and the page read as a pile of panels. */}
      <PageSection index={0}>
        <SectionHeading
          title="Integrity"
          hint="Run on demand — both checks read the whole ledger"
          icon={ShieldCheck}
        />
        <div className="grid gap-sp-6 xl:grid-cols-2">
          <AuditChainPanel />
          <IntegrityPanel />
        </div>
      </PageSection>

      <PageSection index={1}>
        <SectionHeading title="Retention" hint="Destructive, and audited" icon={Archive} />
        <RetentionPanel />
      </PageSection>

      <PageSection index={2}>
        <SectionHeading title="The record" hint="Append-only, newest first" icon={ScrollText} />
        <AuditLedgerTable />
      </PageSection>
    </>
  );
}

function AuditChainPanel() {
  const verify = useMutation({ mutationFn: () => verifyAuditChain() });

  return (
    <Card>
      <CardHeader
        title="Audit Chain"
        subtitle="Recompute every hash in the ledger and confirm the chain is unbroken."
        icon={Link2}
        action={
          <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
            {verify.isPending ? "Verifying..." : "Verify chain"}
          </Button>
        }
      />
      <div className="mt-sp-6">
        {verify.isError ? (
          <InlineError error={verify.error} />
        ) : verify.data ? (
          <div aria-live="polite" aria-atomic="true">
            <div className="flex items-center gap-sp-5">
              <StatusChip status={checkStatusKey(verify.data.intact)} />
              <span className="t-ui text-ink-1">
                {verify.data.intact
                  ? "Chain intact"
                  : "Chain broken \u2014 investigate immediately"}
              </span>
              <span className="t-label ml-auto text-ink-3">
                {formatInteger(verify.data.entries)} entries
              </span>
            </div>
          </div>
        ) : (
          <p className="t-caption text-ink-4">
            Not run yet. Verification reads the whole ledger, so it runs only when you ask for it.
          </p>
        )}
      </div>
    </Card>
  );
}

function IntegrityPanel() {
  const integrity = useMutation({ mutationFn: () => runIntegrityReport() });

  return (
    <Card>
      <CardHeader
        title="Referential Integrity"
        subtitle="Cross-domain orphan checks plus the audit chain."
        icon={Fingerprint}
        action={
          <Button onClick={() => integrity.mutate()} disabled={integrity.isPending}>
            {integrity.isPending ? "Running..." : "Run check"}
          </Button>
        }
      />
      <div className="mt-sp-6">
        {integrity.isError ? (
          <InlineError error={integrity.error} />
        ) : integrity.data ? (
          <div aria-live="polite" aria-atomic="true">
            <div className="flex items-center gap-sp-5">
              <StatusChip status={checkStatusKey(integrity.data.ok)} />
              <span className="t-ui text-ink-1">
                {integrity.data.ok
                  ? "No orphans, chain intact"
                  : `${formatInteger(totalOrphans(integrity.data))} orphaned row(s)`}
              </span>
            </div>
            <ul className="mt-sp-5">
              {Object.entries(integrity.data.orphans).map(([key, count]) => (
                <li
                  key={key}
                  className="flex items-center gap-sp-5 border-t border-stroke-subtle py-sp-4"
                >
                  <span className="t-caption truncate text-ink-3">{orphanLabel(key)}</span>
                  <Token className="ml-auto">{formatInteger(count)}</Token>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="t-caption text-ink-4">Not run yet.</p>
        )}
      </div>
    </Card>
  );
}

function AuditLedgerTable() {
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(0);

  /* Five rows, fixed. The ledger is a reference surface you scan a page at a time, not a list
   * you read top to bottom, so a taller page buys nothing and costs the panels above it. */
  const pageSize = 5;

  const entries = useInfiniteQuery({
    queryKey: auditKeys.entries(eventType),
    queryFn: ({ pageParam }) =>
      listAuditEntries({
        data: { eventType: eventType || undefined, beforeSeq: pageParam ?? undefined },
      }),
    initialPageParam: null as number | null,
    getNextPageParam: (page) => (page.has_more ? page.next_before_seq : undefined),
  });

  /**
   * The ledger is walked backwards by `beforeSeq`, so there is no total to page against \u2014 hence
   * CursorPager rather than Pager.
   *
   * The important change is that fetched pages now ACCUMULATE IN THE CACHE but only ONE is ever
   * RENDERED. "Load older" previously flattened every fetched page into a single table, so the
   * ledger grew without bound: fifty rows became a hundred became two hundred, and the page height
   * with it. Stepping back through pages stays instant because the data is still cached.
   */
  const fetchedPages = entries.data?.pages ?? [];
  const activePage = fetchedPages[page];
  const rows = activePage?.entries ?? [];

  /* Changing the filter restarts the walk, so any page index from the old filter is meaningless. */
  useEffect(() => setPage(0), [eventType]);

  return (
    <Card padded={false}>
      <div className="p-sp-7">
        <CardHeader
          title="Audit ledger"
          subtitle="Each page is fetched on demand and kept in cache, so stepping back is instant and the page never grows."
          icon={ScrollText}
        />
      </div>
      <TableShell
        minWidth={780}
        bodyAsChild
        busy={entries.isFetchingNextPage || (entries.isFetching && !entries.isPending)}
        toolbar={
          <SearchInput
            placeholder="Filter by event type"
            className="w-full sm:w-[280px]"
            value={eventType}
            onChange={setEventType}
          />
        }
        head={
          <tr>
            <Th>Seq</Th>
            <Th>Event</Th>
            <Th>Reference</Th>
            <Th>Hash</Th>
            <Th align="right">When</Th>
          </tr>
        }
        footer={
          <CursorPager
            page={page}
            loadedPages={fetchedPages.length}
            hasMore={entries.hasNextPage}
            onPageChange={setPage}
            onLoadMore={() => {
              void entries.fetchNextPage().then(() => setPage((current) => current + 1));
            }}
            loading={entries.isFetchingNextPage}
            rowsOnPage={rows.length}
          />
        }
      >
        <TableBodySwap pageKey={`${page}-${eventType}`}>
          {entries.isPending ? (
            <TableSkeleton rows={pageSize} columns={5} />
          ) : entries.isError && entries.data === undefined ? (
            <TableErrorRow
              columns={5}
              error={entries.error}
              onRetry={() => void entries.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={5}>
                <EmptyState
                  icon={ShieldCheck}
                  title="No audit entries"
                  description="Nothing has been recorded yet."
                />
              </td>
            </tr>
          ) : (
            rows.map((entry, index) => {
              /* Link verification compares against the next-older row. At a page boundary that
               * row lives on the following page, so the last row of a page has nothing to check
               * against \u2014 `older` is undefined there and no claim is made either way. */
              const older = rows[index + 1];
              const canVerifyLink = older !== undefined;
              const linked = isLinked(entry, older);
              return (
                <tr
                  key={entry.seq}
                  className="transition-colors duration-[120ms] hover:bg-surface-3"
                >
                  <Td>
                    <Token>{entry.seq}</Token>
                  </Td>
                  <Td>{eventLabel(entry.event_type)}</Td>
                  <Td>
                    <span className="block max-w-[28ch] truncate">
                      {entry.entity_reference ?? "\u2014"}
                    </span>
                  </Td>
                  <Td>
                    <span className="flex items-center gap-sp-4">
                      <Token>{shortHash(entry.entry_hash)}</Token>
                      {canVerifyLink && !linked ? (
                        <span className="t-caption whitespace-nowrap text-ink-3">
                          link mismatch
                        </span>
                      ) : null}
                    </span>
                  </Td>
                  <Td align="right">
                    <span className="t-mono whitespace-nowrap text-ink-3">
                      {formatInstant(entry.created_at)}
                    </span>
                  </Td>
                </tr>
              );
            })
          )}
        </TableBodySwap>
      </TableShell>
    </Card>
  );
}
