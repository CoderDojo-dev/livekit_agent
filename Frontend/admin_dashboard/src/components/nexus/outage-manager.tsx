import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Plus, RadioTower, SquarePen } from "lucide-react";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  IconButton,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  TextField,
  Token,
} from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { AreaPicker } from "@/components/nexus/area-picker";
import { InlineError, TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { Pager } from "@/components/nexus/pager";
import { TableBodySwap } from "@/components/nexus/motion";
import {
  OUTAGE_CAUSES,
  OUTAGE_SEVERITIES,
  createOutage,
  listOutages,
  updateOutage,
  type OutageEntry,
} from "@/lib/api/reference.server";
import { referenceKeys } from "@/lib/nexus/query-keys";
import { clampPage, slicePage } from "@/lib/nexus/paginate";
import { cn } from "@/lib/utils";

/**
 * Network incidents — the one admin surface the voice agent reads back verbatim.
 *
 * WHY THIS MATTERS MORE THAN A NORMAL CRUD SCREEN
 * When a caller says "I have no signal in Ariana", the agent resolves that place against the geo
 * referential, walks the hierarchy, and reads the ACTIVE outages here. So:
 *   - declaring an outage makes the agent stop telling callers in that area the network is fine;
 *   - `description_fr` is not a note. It is the sentence the caller hears.
 *
 * That is why the French description is required and is labelled as spoken text rather than as a
 * comment field, and why resolving an incident is a first-class action rather than a delete.
 */

const PAGE_SIZE = 5;

/** "fiber_cut" -> "Fiber cut". The stored value is the constraint's vocabulary, not the label. */
function humanise(value: string | null): string {
  if (!value) return "—";
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, " ");
}

function severityStatus(severity: string): string {
  // Reuses the existing status vocabulary rather than inventing three new chips.
  if (severity === "critical") return "escalated";
  if (severity === "major") return "open";
  return "pending";
}

export function OutageManager({ canEdit }: { canEdit: boolean }) {
  const [activeOnly, setActiveOnly] = useState(true);
  const [page, setPage] = useState(0);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<OutageEntry | null>(null);

  const outages = useQuery({
    queryKey: referenceKeys.outages(activeOnly),
    queryFn: () => listOutages({ data: { activeOnly } }),
  });

  const rows = outages.data?.outages ?? [];
  const safePage = clampPage(page, rows.length, PAGE_SIZE);
  const visible = slicePage(rows, safePage, PAGE_SIZE);

  return (
    <Card padded={false} className="overflow-hidden">
      <div className="p-sp-7">
        <CardHeader
          icon={RadioTower}
          title="Network incidents"
          subtitle="What the agent tells callers in an affected area. The French description is spoken aloud."
          action={
            <div className="flex flex-wrap items-center gap-sp-4">
              <Segmented
                groupId="outage-scope"
                items={["Active", "All"]}
                active={activeOnly ? "Active" : "All"}
                onSelect={(label) => {
                  setActiveOnly(label === "Active");
                  setPage(0);
                }}
              />
              {canEdit ? (
                <Button icon={Plus} onClick={() => setCreating(true)}>
                  Declare
                </Button>
              ) : null}
            </div>
          }
        />
      </div>

      <TableShell
        minWidth={920}
        bodyAsChild
        busy={outages.isFetching && !outages.isPending}
        head={
          <tr>
            <Th>Area</Th>
            <Th>Severity</Th>
            <Th>Cause</Th>
            <Th>What the agent says</Th>
            <Th>Status</Th>
            <Th align="right" />
          </tr>
        }
        footer={
          <Pager
            page={safePage}
            pageSize={PAGE_SIZE}
            total={rows.length}
            onPageChange={setPage}
            noun="incidents"
            className="w-full"
          />
        }
      >
        <TableBodySwap pageKey={`${safePage}-${activeOnly}`}>
          {outages.isPending ? (
            <TableSkeleton columns={6} rows={PAGE_SIZE} />
          ) : outages.isError ? (
            <TableErrorRow columns={6} error={outages.error} onRetry={() => outages.refetch()} />
          ) : visible.length === 0 ? (
            <tr>
              <td colSpan={6}>
                <EmptyState
                  icon={CheckCircle2}
                  compact
                  title={activeOnly ? "No active incident" : "No incident on record"}
                  description={
                    activeOnly
                      ? "The agent is telling callers the network is normal everywhere."
                      : "Nothing has been declared yet."
                  }
                />
              </td>
            </tr>
          ) : (
            visible.map((row) => (
              <tr
                key={row.id}
                className="group/row transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <Td>
                  <span className="t-ui block truncate text-ink-1">
                    {row.area_name ?? row.area ?? "—"}
                  </span>
                  <span className="t-mono-s block truncate text-ink-4">{row.area_code}</span>
                </Td>
                <Td>
                  <StatusChip status={severityStatus(row.severity)} />
                </Td>
                <Td>
                  <Token mono={false}>{humanise(row.cause)}</Token>
                </Td>
                <Td>
                  {/* Truncated here, full text on hover: this is prose, and the table is a list. */}
                  <span
                    className="t-caption block max-w-[42ch] truncate text-ink-3"
                    title={row.description_fr ?? undefined}
                  >
                    {row.description_fr ?? "—"}
                  </span>
                </Td>
                <Td>
                  <Token strong={!row.resolved}>{row.resolved ? "Resolved" : "Live"}</Token>
                </Td>
                <Td align="right">
                  {canEdit ? (
                    <span className="inline-flex opacity-0 transition-opacity duration-[120ms] group-hover/row:opacity-100 focus-within:opacity-100">
                      <IconButton
                        size="sm"
                        label={`Edit incident in ${row.area_name ?? row.area_code}`}
                        icon={SquarePen}
                        onClick={() => setEditing(row)}
                      />
                    </span>
                  ) : null}
                </Td>
              </tr>
            ))
          )}
        </TableBodySwap>
      </TableShell>

      {creating ? <OutageDialog onClose={() => setCreating(false)} /> : null}
      {editing ? <OutageDialog outage={editing} onClose={() => setEditing(null)} /> : null}
    </Card>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Declare / edit
 * ------------------------------------------------------------------------------------------- */

function OutageDialog({ outage, onClose }: { outage?: OutageEntry; onClose: () => void }) {
  const queryClient = useQueryClient();
  const isEdit = outage !== undefined;

  const [areaCode, setAreaCode] = useState(outage?.area_code ?? "");
  const [severity, setSeverity] = useState<(typeof OUTAGE_SEVERITIES)[number]>(
    (outage?.severity as (typeof OUTAGE_SEVERITIES)[number]) ?? "minor",
  );
  const [cause, setCause] = useState<string>(outage?.cause ?? "");
  const [services, setServices] = useState(outage?.affected_services ?? "");
  const [fr, setFr] = useState(outage?.description_fr ?? "");
  const [ar, setAr] = useState(outage?.description_ar ?? "");
  const [resolved, setResolved] = useState(outage?.resolved ?? false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: referenceKeys.outagesAll });

  const save = useMutation({
    mutationFn: async () => {
      if (isEdit) {
        return updateOutage({
          data: {
            outageId: outage.id,
            severity,
            resolved,
            ...(fr.trim() ? { descriptionFr: fr.trim() } : {}),
            descriptionAr: ar.trim(),
          },
        });
      }
      return createOutage({
        data: {
          areaCode: areaCode.trim().toUpperCase(),
          severity,
          ...(cause ? { cause: cause as (typeof OUTAGE_CAUSES)[number] } : {}),
          ...(services.trim() ? { affectedServices: services.trim() } : {}),
          descriptionFr: fr.trim(),
          ...(ar.trim() ? { descriptionAr: ar.trim() } : {}),
        },
      });
    },
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });

  const canSave = fr.trim().length > 0 && (isEdit || areaCode.trim().length > 0);

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? "Edit incident" : "Declare a network incident"}
      description={
        isEdit
          ? `${outage.area_name ?? outage.area_code}`
          : "The agent will report this to any caller in the affected area."
      }
      className="max-w-[620px]"
      footer={
        <>
          <Button onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => save.mutate()}
            disabled={!canSave || save.isPending}
          >
            {save.isPending ? "Saving…" : isEdit ? "Save changes" : "Declare incident"}
          </Button>
        </>
      }
    >
      <div className="space-y-sp-6">
        {!isEdit ? (
          /* Searched by NAME, submitted as a code. An operator declaring an incident knows they
           * mean Ariana, not that Ariana is TN-12. */
          <AreaPicker
            label="Affected area"
            value={areaCode}
            onChange={(code) => setAreaCode(code)}
          />
        ) : null}

        <div>
          <p className="t-micro mb-sp-3 text-ink-5">Severity</p>
          <Segmented
            groupId="outage-severity"
            items={OUTAGE_SEVERITIES.map((s) => humanise(s))}
            active={humanise(severity)}
            onSelect={(label) => {
              const found = OUTAGE_SEVERITIES.find((s) => humanise(s) === label);
              if (found) setSeverity(found);
            }}
          />
        </div>

        {!isEdit ? (
          <div>
            <label htmlFor="outage-cause" className="t-micro mb-sp-3 block text-ink-5">
              Cause
            </label>
            <select
              id="outage-cause"
              value={cause}
              onChange={(event) => setCause(event.target.value)}
              className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-ui text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
            >
              <option value="">Not stated</option>
              {OUTAGE_CAUSES.map((option) => (
                <option key={option} value={option}>
                  {humanise(option)}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {!isEdit ? (
          <TextField
            label="Affected services"
            placeholder="data,voice"
            value={services}
            onChange={(event) => setServices(event.target.value)}
          />
        ) : null}

        {/* The spoken text. Labelled as speech, not as a note. */}
        <div>
          <label htmlFor="outage-fr" className="t-micro mb-sp-3 block text-ink-5">
            What the agent says (French) — required
          </label>
          <textarea
            id="outage-fr"
            rows={3}
            value={fr}
            onChange={(event) => setFr(event.target.value)}
            placeholder="Coupure de fibre dans votre zone. Rétablissement prévu ce soir."
            className="w-full resize-y rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 placeholder:text-ink-5 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
          />
          <p className="t-caption mt-sp-2 text-ink-5">
            Callers hear this sentence. French is also the fallback for every other language.
          </p>
        </div>

        <div>
          <label htmlFor="outage-ar" className="t-micro mb-sp-3 block text-ink-5">
            Arabic (optional)
          </label>
          <textarea
            id="outage-ar"
            rows={2}
            dir="rtl"
            value={ar}
            onChange={(event) => setAr(event.target.value)}
            className="w-full resize-y rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
          />
        </div>

        {isEdit ? (
          <div className="flex flex-wrap items-center justify-between gap-sp-5 border-t border-stroke-subtle pt-sp-6">
            <div className="min-w-0">
              <p className="t-body-strong text-ink-1">Resolved</p>
              <p className="t-caption mt-sp-2 max-w-[52ch] text-ink-4">
                Resolving stops the agent reporting it and stamps an end time.
              </p>
            </div>
            <button
              type="button"
              aria-pressed={resolved}
              onClick={() => setResolved((value) => !value)}
              className={cn(
                "inline-flex h-[28px] items-center gap-sp-3 rounded-r-2 border px-sp-5 t-label transition-colors duration-[120ms]",
                resolved
                  ? "border-stroke-ink bg-surface-5 text-ink-1"
                  : "border-stroke-default text-ink-4 hover:text-ink-2",
              )}
            >
              <CheckCircle2 size={13} strokeWidth={1.5} aria-hidden="true" />
              {resolved ? "Resolved" : "Still live"}
            </button>
          </div>
        ) : null}

        {!isEdit ? (
          <p className="t-caption flex items-start gap-sp-3 text-ink-4">
            <AlertTriangle size={13} strokeWidth={1.5} className="mt-[2px] shrink-0" />
            <span>
              This takes effect immediately. The next caller from this area will be told about it.
            </span>
          </p>
        ) : null}

        {save.isError ? <InlineError error={save.error} /> : null}
      </div>
    </Modal>
  );
}
