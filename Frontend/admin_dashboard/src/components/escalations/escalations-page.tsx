import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState, ListSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { PageSwap } from "@/components/nexus/motion";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { useAdaptivePageSize, ROW_HEIGHT } from "@/hooks/use-adaptive-page-size";
import { errorMessage } from "@/lib/api/errors";
import {
  closeEscalation,
  listEscalations,
  type Escalation,
  type EscalationResolution,
} from "@/lib/api/escalations.server";
import {
  dossierEntries,
  escalationCustomerId,
  escalationCustomerName,
  escalationMatches,
  escalationStatusKey,
  resolutionLabel,
  targetLabel,
  triggerLabel,
} from "@/lib/nexus/escalation-view";
import { formatInstant } from "@/lib/nexus/audit-view";
import { cn } from "@/lib/utils";

// The cookbook prescribes exporting the query-key factory from this page component file;
// the react-refresh rule cannot allow a function-valued constant export next to a component.
// eslint-disable-next-line react-refresh/only-export-components
export const escalationKeys = {
  all: ["escalations"] as const,

  list: (scope: "open" | "all") => [...escalationKeys.all, scope] as const,
};

const SCOPE_OPTIONS = [
  { id: "open", label: "Open" },
  { id: "all", label: "All" },
];

const RESOLUTIONS: { id: EscalationResolution; label: string }[] = [
  { id: "transferred", label: "Transferred" },
  { id: "queued", label: "Queued" },
  { id: "callback_scheduled", label: "Callback scheduled" },
  { id: "resolved", label: "Resolved" },
];

export function EscalationsPage() {
  const [scope, setScope] = useState<"open" | "all">("open");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  /**
   * Handoffs are paged rather than scrolled.
   *
   * The list previously sat in a `max-h-[640px] overflow-y-auto` box nested inside the page
   * scroll — the same scroll trap /calls had. Paging keeps the dossier beside it anchored and
   * leaves one scrollbar on the page.
   */
  const pageSize = useAdaptivePageSize({
    rowHeight: ROW_HEIGHT.listItem,
    chrome: 440,
    min: 5,
    max: 10,
    fallback: 6,
  });

  const query = useQuery({
    queryKey: escalationKeys.list(scope),
    queryFn: () => listEscalations({ data: { scope } }),
  });

  const queryClient = useQueryClient();

  const close = useMutation({
    mutationFn: (vars: { id: string; resolution: EscalationResolution }) =>
      closeEscalation({ data: vars }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: escalationKeys.list(scope) });
    },
  });

  const rows = useMemo(
    () => (query.data?.escalations ?? []).filter((e) => escalationMatches(e, q)),
    [query.data, q],
  );

  useEffect(() => setPage(0), [q, scope, pageSize]);
  const safePage = clampPage(page, rows.length, pageSize);
  const visible = slicePage(rows, safePage, pageSize);

  /* Selection resolves against the whole filtered set, not just the visible page: a dossier
   * opened on page 1 must survive a step to page 2 rather than silently snapping to another
   * handoff. The fallback is the first row of the CURRENT page, so an unselected view always
   * shows something that is actually on screen. */
  const current: Escalation | undefined = rows.find((e) => e.id === selected) ?? visible[0];

  return (
    <PageSection className="grid gap-sp-6 xl:grid-cols-[360px_1fr]">
      {/* ---------- List ---------- */}
      <Card padded={false} className="overflow-hidden">
        <div className="flex items-center justify-between gap-sp-5 border-b border-stroke-subtle p-sp-6">
          <span className="t-micro text-ink-5">Handoffs</span>
          <Segmented
            items={SCOPE_OPTIONS.map((o) => o.label)}
            active={SCOPE_OPTIONS.find((o) => o.id === scope)?.label ?? "Open"}
            onSelect={(label) => {
              setScope(SCOPE_OPTIONS.find((o) => o.label === label)?.id as "open" | "all");
              setSelected(null);
            }}
          />
        </div>

        <div className="border-b border-stroke-subtle p-sp-6">
          <SearchInput
            placeholder="Search customer, id, trigger, target or session"
            value={q}
            onChange={setQ}
          />
        </div>

        {query.isPending ? (
          <ListSkeleton rows={pageSize} />
        ) : query.isError ? (
          <div className="p-sp-6">
            <ErrorState error={query.error} onRetry={() => void query.refetch()} />
          </div>
        ) : rows.length === 0 ? (
          <div className="p-sp-7">
            <EmptyState
              icon={ShieldAlert}
              title={scope === "open" ? "No open escalations" : "No escalations recorded"}
              description={
                scope === "open"
                  ? "Every handoff has been closed out."
                  : "The agent has not handed a call to a human yet."
              }
            />
          </div>
        ) : (
          <>
            <PageSwap pageKey={safePage}>
              <ul>
                {visible.map((e) => {
                  const active = current?.id === e.id;
                  return (
                    <li key={e.id}>
                      <button
                        type="button"
                        onClick={() => setSelected(e.id)}
                        className={cn(
                          "flex w-full items-start gap-sp-5 border-b border-stroke-subtle px-sp-6 py-sp-5 text-left transition-colors duration-[120ms]",
                          active ? "bg-surface-3" : "hover:bg-surface-3/60",
                        )}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-sp-3">
                            <span className="t-ui block truncate text-ink-1">
                              {escalationCustomerName(e)}
                            </span>
                            {e.customer_vip === true ? <Token strong>VIP</Token> : null}
                          </span>
                          <span className="t-caption block truncate text-ink-4">
                            {triggerLabel(e.trigger)} · {targetLabel(e.target)}
                          </span>
                          <span className="t-mono-s block truncate text-ink-5">
                            {escalationCustomerId(e)}
                          </span>
                        </span>
                        <StatusChip status={escalationStatusKey(e.resolution)} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </PageSwap>
            <div className="border-t border-stroke-subtle px-sp-6 py-sp-5">
              <Pager
                page={safePage}
                pageSize={pageSize}
                total={rows.length}
                onPageChange={setPage}
                noun="handoffs"
                busy={query.isFetching && !query.isPending}
              />
              <p className="t-caption mt-sp-3 text-ink-5">Most recent first</p>
            </div>
          </>
        )}
      </Card>

      {/* ---------- Dossier ---------- */}
      <Card padded={false}>
        {!current ? (
          <div className="p-sp-7">
            <EmptyState
              icon={ShieldAlert}
              title="No handoff selected"
              description="Choose an escalation to read the dossier handed to the human."
            />
          </div>
        ) : (
          <>
            <div className="p-sp-7">
              <CardHeader
                title={triggerLabel(current.trigger)}
                subtitle={`Handed to ${targetLabel(current.target)}`}
              />
            </div>

            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Outcome</span>
              {current.resolution ? (
                <span className="ml-auto flex items-center gap-sp-4">
                  <span className="t-ui text-ink-2">{resolutionLabel(current.resolution)}</span>
                  <StatusChip status={escalationStatusKey(current.resolution)} />
                </span>
              ) : (
                <span className="ml-auto flex flex-wrap items-center justify-end gap-sp-3">
                  {RESOLUTIONS.map((r) => (
                    <Button
                      key={r.id}
                      size="sm"
                      variant="secondary"
                      disabled={close.isPending}
                      onClick={() => close.mutate({ id: current.id, resolution: r.id })}
                    >
                      {r.label}
                    </Button>
                  ))}
                </span>
              )}
            </div>
            {close.isError ? (
              <p role="alert" className="t-caption px-sp-7 pb-sp-5 text-ink-2">
                {errorMessage(close.error)}
              </p>
            ) : null}

            {/* Batch 5 — customer identity projection, always before the session row. */}
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Customer</span>
              <span className="ml-auto flex items-center gap-sp-4">
                <span className="t-ui text-ink-2">{escalationCustomerName(current)}</span>
                {current.customer_vip === true ? <Token strong>VIP</Token> : null}
                <span className="t-mono-s truncate text-ink-5">
                  {escalationCustomerId(current)}
                </span>
              </span>
            </div>

            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Session</span>
              <span className="t-mono ml-auto truncate text-ink-3">{current.session_id}</span>
            </div>

            {/* Batch 1 / C13 — created_at is now on the wire. */}
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Raised</span>
              <span className="t-mono ml-auto text-ink-3">
                {current.created_at ? formatInstant(current.created_at) : "\u2014"}
              </span>
            </div>

            <div className="mt-sp-7 px-sp-7">
              <CardHeader
                title="Context dossier"
                subtitle="Exactly what the agent handed over. Recorded at handoff time."
              />
            </div>

            {dossierEntries(current.dossier).length === 0 ? (
              <div className="px-sp-7 pb-sp-7 pt-sp-5">
                <p className="t-caption text-ink-5">The dossier is empty.</p>
              </div>
            ) : (
              <ul className="mt-sp-5">
                {dossierEntries(current.dossier).map((d) => (
                  <li
                    key={d.key}
                    className="border-t border-stroke-subtle px-sp-7 py-sp-5 last:border-b-0"
                  >
                    {d.long ? (
                      <div className="min-w-0">
                        <p className="t-label text-ink-3">{d.label}</p>
                        <p className="t-mono mt-sp-3 break-words text-ink-2">{d.value}</p>
                      </div>
                    ) : (
                      <div className="flex items-center gap-sp-5">
                        <span className="t-label text-ink-3">{d.label}</span>
                        <span className="t-mono-l ml-auto truncate text-ink-1">{d.value}</span>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </Card>
    </PageSection>
  );
}
