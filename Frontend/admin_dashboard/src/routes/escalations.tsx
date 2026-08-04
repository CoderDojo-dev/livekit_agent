import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import {
  Card,
  CardHeader,
  EmptyState,
  SearchInput,
  Segmented,
  StatusChip,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { CardSkeleton, ErrorState } from "@/components/nexus/states";
import { listEscalations, type Escalation } from "@/lib/api/escalations.server";
import {
  createdLabel,
  dossierEntries,
  escalationMatches,
  escalationStatusKey,
  resolutionLabel,
  targetLabel,
  triggerLabel,
} from "@/lib/nexus/escalation-view";
import { escalationKeys } from "@/lib/nexus/query-keys";
import { cn } from "@/lib/utils";

const SCOPE_OPTIONS = [
  { id: "open", label: "Open" },
  { id: "all", label: "All" },
];

export const Route = createFileRoute("/escalations")({
  head: () => ({
    meta: [
      { title: "Escalations — Nexus" },
      {
        name: "description",
        content:
          "Handoffs from the AI to a manager agent or a human advisor, with the context dossier.",
      },
      { property: "og:title", content: "Escalations — Nexus" },
      { property: "og:description", content: "Every AI-to-human handoff and its dossier." },
    ],
  }),
  component: EscalationsPage,
});

function EscalationsPage() {
  const [scope, setScope] = useState<"open" | "all">("open");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const query = useQuery({
    queryKey: escalationKeys.list(scope),
    queryFn: () => listEscalations({ data: { scope } }),
  });

  const rows = useMemo(
    () => (query.data?.escalations ?? []).filter((e) => escalationMatches(e, q)),
    [query.data, q],
  );

  const current: Escalation | undefined = rows.find((e) => e.id === selected) ?? rows[0];

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
          <SearchInput placeholder="Search trigger, target or session" value={q} onChange={setQ} />
        </div>

        {query.isPending ? (
          <div className="p-sp-6">
            <CardSkeleton />
          </div>
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
            <ul className="max-h-[640px] overflow-y-auto">
              {rows.map((e) => {
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
                        <span className="t-ui block truncate text-ink-1">
                          {triggerLabel(e.trigger)}
                        </span>
                        <span className="t-caption block truncate text-ink-4">
                          {targetLabel(e.target)}
                        </span>
                      </span>
                      <StatusChip status={escalationStatusKey(e.resolution)} />
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-6 py-sp-5">
              <Token>{rows.length} shown</Token>
              <span className="t-caption ml-auto text-ink-5">Most recent first</span>
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
              <span className="ml-auto flex items-center gap-sp-4">
                <span className="t-ui text-ink-2">{resolutionLabel(current.resolution)}</span>
                <StatusChip status={escalationStatusKey(current.resolution)} />
              </span>
            </div>

            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Session</span>
              <span className="t-mono ml-auto truncate text-ink-3">{current.session_id}</span>
            </div>

            {/* Batch 1 / C13 — created_at is now on the wire. */}
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Raised</span>
              <span className="t-mono ml-auto text-ink-3">{createdLabel(current.created_at)}</span>
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
