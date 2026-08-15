import { useState } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { AlertTriangle, ShieldCheck } from "lucide-react";
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
  TextField,
  SearchInput,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableSkeleton, InlineError, TableErrorRow } from "@/components/nexus/states";
import { Modal } from "@/components/nexus/modal";
import { RetentionPanel } from "@/components/nexus/retention-panel";
import { verifyAuditChain, runIntegrityReport, listAuditEntries } from "@/lib/api/audit.server";
import { changePassword, revokeAllSessions } from "@/lib/api/auth.server";
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
import { hasRank } from "@/lib/api/session";
import { formatInteger } from "@/lib/nexus/format";
import { Route as RootRoute } from "@/routes/__root";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings \u2014 Nexus" },
      { name: "description", content: "Audit chain, referential integrity and data retention." },
      { property: "og:title", content: "Settings \u2014 Nexus" },
      { property: "og:description", content: "Administrative operations for the platform." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { session } = RootRoute.useRouteContext();
  const isAdmin = session !== null && hasRank(session, "administrateur");

  return (
    <>
      <PageSection>
        <AccountSecurityPanel />
      </PageSection>

      {isAdmin ? (
        <>
          <PageSection className="grid gap-sp-6 xl:grid-cols-2">
            <AuditChainPanel />
            <IntegrityPanel />
          </PageSection>

          <PageSection>
            <RetentionPanel />
          </PageSection>

          <PageSection>
            <AuditLedgerTable />
          </PageSection>
        </>
      ) : (
        <PageSection>
          <Card>
            <EmptyState
              icon={ShieldCheck}
              title="Administrative controls hidden"
              description="Audit verification, integrity checks and data retention are restricted to administrators."
            />
          </Card>
        </PageSection>
      )}
    </>
  );
}

function AccountSecurityPanel() {
  const router = useRouter();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [revokeOpen, setRevokeOpen] = useState(false);

  const change = useMutation({
    mutationFn: () => changePassword({ data: { currentPassword: current, newPassword: next } }),
    onSuccess: () => {
      void router.invalidate().then(() => router.navigate({ to: "/login" }));
    },
  });

  const revoke = useMutation({
    mutationFn: () => revokeAllSessions(),
    onSuccess: () => {
      setRevokeOpen(false);
      void router.invalidate().then(() => router.navigate({ to: "/login" }));
    },
  });

  let localError: string | null = null;
  if (current === "" || next === "" || confirm === "") {
    localError = "All fields are required.";
  } else if (next.length < 10) {
    localError = "Choose a password of at least 10 characters.";
  } else if (next === current) {
    localError = "Choose a password you have not used here before.";
  } else if (next !== confirm) {
    localError = "Passwords do not match.";
  }

  return (
    <Card>
      <CardHeader
        title="Account Security"
        subtitle="Change your password or sign out of every device."
      />

      <div className="mt-sp-6 flex flex-wrap items-end gap-sp-5">
        <TextField
          label="Current password"
          type="password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <TextField
          label="New password"
          type="password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <TextField
          label="Confirm new password"
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button onClick={() => change.mutate()} disabled={localError !== null || change.isPending}>
          {change.isPending ? "Changing..." : "Change password"}
        </Button>
      </div>

      {change.isError ? (
        <div className="mt-sp-5">
          <InlineError error={change.error} />
        </div>
      ) : null}
      {localError !== null && !change.isError ? (
        <p className="t-caption mt-sp-5 text-ink-3">{localError}</p>
      ) : null}

      <div className="mt-sp-6 flex items-center justify-between gap-sp-5 border-t border-stroke-subtle pt-sp-5">
        <p className="t-caption max-w-[48ch] text-ink-4">
          Signing out of all devices closes every session on this account, including this one.
        </p>
        <Button onClick={() => setRevokeOpen(true)} disabled={revoke.isPending}>
          {revoke.isPending ? "Signing out..." : "Sign out of all devices"}
        </Button>
      </div>

      {revoke.isError ? (
        <div className="mt-sp-5">
          <InlineError error={revoke.error} />
        </div>
      ) : null}

      <Modal
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        title="Sign out of all devices"
        description="Every session for this account will be closed. You will have to sign in again."
        footer={
          <>
            <Button onClick={() => setRevokeOpen(false)}>Cancel</Button>
            <Button onClick={() => revoke.mutate()} disabled={revoke.isPending}>
              {revoke.isPending ? "Signing out..." : "Sign out everywhere"}
            </Button>
          </>
        }
      >
        <div className="flex items-start gap-sp-5">
          <AlertTriangle
            size={16}
            strokeWidth={1.5}
            aria-hidden="true"
            className="mt-sp-2 text-ink-3"
          />
          <p className="t-ui text-ink-1">
            This cannot be undone. Sessions on other browsers and devices will stop working
            immediately.
          </p>
        </div>
      </Modal>
    </Card>
  );
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
