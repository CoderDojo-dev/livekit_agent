import { useState } from "react";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Card, CardHeader, Button, StatusChip, Token, EmptyState, TableShell, Th, Td, SearchInput } from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableSkeleton, InlineError, TableErrorRow } from "@/components/nexus/states";
import { RetentionPanel } from "@/components/nexus/retention-panel";
import { verifyAuditChain, runIntegrityReport, listAuditEntries } from "@/lib/api/audit.server";
import { auditKeys } from "@/lib/nexus/query-keys";
import { checkStatusKey, orphanLabel, totalOrphans, shortHash, eventLabel, formatInstant, isLinked } from "@/lib/nexus/audit-view";
import { hasRank } from "@/lib/api/session";
import { formatInteger } from "@/lib/nexus/format";

export const Route = createFileRoute("/audit")({
  beforeLoad: ({ context }) => {
    if (context.session === null || !hasRank(context.session, "administrateur")) {
      throw redirect({ to: "/settings" });
    }
  },
  head: () => ({ meta: [
    { title: "Audit ΓÇö Nexus" },
    { name: "description", content: "Administrator-only audit ledger, integrity verification and retention operations." },
    { property: "og:title", content: "Audit ΓÇö Nexus" },
    { property: "og:description", content: "Audit ledger and operational data controls." },
  ] }),
  component: AuditPage,
});

function AuditPage() {
  return (<>
    <PageSection className="grid gap-sp-6 xl:grid-cols-2"><AuditChainPanel /><IntegrityPanel /></PageSection>
    <PageSection><RetentionPanel /></PageSection>
    <PageSection><AuditLedgerTable /></PageSection>
  </>);
}

function AuditChainPanel() {
  const verify = useMutation({ mutationFn: () => verifyAuditChain() });

  return (
    <Card>
      <CardHeader
        title="Audit Chain"
        subtitle="Recompute every hash in the ledger and confirm the chain is unbroken."
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
          <div className="flex items-center gap-sp-5">
            <StatusChip status={checkStatusKey(verify.data.intact)} />
            <span className="t-ui text-ink-1">
              {verify.data.intact ? "Chain intact" : "Chain broken \u2014 investigate immediately"}
            </span>
            <span className="t-label ml-auto text-ink-3">
              {formatInteger(verify.data.entries)} entries
            </span>
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
          <>
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
          </>
        ) : (
          <p className="t-caption text-ink-4">Not run yet.</p>
        )}
      </div>
    </Card>
  );
}

function AuditLedgerTable() {
  const [eventType, setEventType] = useState("");
  const entries = useInfiniteQuery({
    queryKey: auditKeys.entries(eventType),
    queryFn: ({ pageParam }) =>
      listAuditEntries({
        data: { eventType: eventType || undefined, beforeSeq: pageParam ?? undefined },
      }),
    initialPageParam: null as number | null,
    getNextPageParam: (page) => (page.has_more ? page.next_before_seq : undefined),
  });

  const rows = entries.data?.pages.flatMap((page) => page.entries) ?? [];

  return (
    <Card padded={false}>
      <div className="p-sp-7">
        <CardHeader title="Audit Ledger" subtitle="The 50 most recent entries, newest first." />
      </div>
      <TableShell
        toolbar={
          <SearchInput
            placeholder="Filter by event type"
            className="w-[280px]"
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
            <Th>When</Th>
          </tr>
        }
        footer={
          <>
            <span className="t-label text-ink-3">{formatInteger(rows.length)} entries loaded</span>
            <Button
              size="sm"
              onClick={() => void entries.fetchNextPage()}
              disabled={!entries.hasNextPage || entries.isFetchingNextPage}
            >
              {entries.isFetchingNextPage ? "Loading..." : "Load older"}
            </Button>
          </>
        }
      >
        {entries.isPending ? (
          <TableSkeleton rows={6} columns={5} />
        ) : entries.isError && entries.data === undefined ? (
          <TableErrorRow columns={5} error={entries.error} onRetry={() => void entries.refetch()} />
        ) : rows.length === 0 ? (
          <tr>
            <td colSpan={5} className="h-[52px] border-b border-stroke-subtle px-sp-6">
              <EmptyState
                icon={ShieldCheck}
                title="No audit entries"
                description="Nothing has been recorded yet."
              />
            </td>
          </tr>
        ) : (
          rows.map((entry, index) => {
            const older = rows[index + 1];
            const canVerifyLink = older !== undefined;
            const linked = isLinked(entry, older);
            return (
              <tr key={entry.seq}>
                <Td>
                  <Token>{entry.seq}</Token>
                </Td>
                <Td>{eventLabel(entry.event_type)}</Td>
                <Td>{entry.entity_reference ?? "\u2014"}</Td>
                <Td>
                  <Token>{shortHash(entry.entry_hash)}</Token>
                  {canVerifyLink && !linked ? (
                    <span className="t-caption ml-sp-4 text-ink-3">link mismatch</span>
                  ) : null}
                </Td>
                <Td>{formatInstant(entry.created_at)}</Td>
              </tr>
            );
          })
        )}
      </TableShell>
    </Card>
  );
}
