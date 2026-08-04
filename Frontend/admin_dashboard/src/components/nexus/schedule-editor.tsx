import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { Modal } from "@/components/nexus/modal";
import {
  Button,
  Card,
  IconButton,
  Segmented,
  Tabs,
  TextField,
  Token,
} from "@/components/nexus/primitives";
import { CardSkeleton, ErrorState, InlineError } from "@/components/nexus/states";
import {
  createTimeOff,
  deleteTimeOff,
  getAdvisorWeek,
  replaceSchedule,
} from "@/lib/api/availability.server";
import type { Advisor } from "@/lib/api/advisors.server";
import { availabilityKeys } from "@/lib/nexus/query-keys";
import {
  businessLocalToIso,
  formatBusinessInstant,
  gridToWindows,
  newUid,
  shiftsToGrid,
  validateGrid,
  weeklyHours,
  WEEKDAY_LABELS,
  type GridWindow,
} from "@/lib/nexus/availability-view";
import { errorMessage } from "@/lib/api/errors";

const TABS = [
  { id: "grid", label: "Weekly grid" },
  { id: "time-off", label: "Upcoming time off" },
];

export function ScheduleEditor({ advisor, onClose }: { advisor: Advisor; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("grid");
  const [grid, setGrid] = useState<GridWindow[] | null>(null);
  const [gridError, setGridError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const weekQuery = useQuery({
    queryKey: availabilityKeys.week(advisor.id),
    queryFn: () => getAdvisorWeek({ data: { advisorId: advisor.id } }),
  });

  // Seed the editable grid once the server state arrives.
  useEffect(() => {
    if (weekQuery.data && grid === null) {
      setGrid(shiftsToGrid(weekQuery.data.shifts));
    }
  }, [weekQuery.data, grid]);

  const timeZone = weekQuery.data?.timezone ?? "UTC";

  const saveGrid = useMutation({
    mutationFn: (windows: ReturnType<typeof gridToWindows>) =>
      replaceSchedule({ data: { advisorId: advisor.id, windows } }),
    onSuccess: (result) => {
      setGrid(shiftsToGrid(result.shifts));
      setConfirmClear(false);
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const addTimeOff = useMutation({
    mutationFn: (input: { starts_at: string; ends_at: string; reason?: string }) =>
      createTimeOff({ data: { advisorId: advisor.id, ...input } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const removeTimeOff = useMutation({
    mutationFn: (timeOffId: string) => deleteTimeOff({ data: { timeOffId } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityKeys.all });
    },
  });

  const dirty = useMemo(() => {
    if (!grid || !weekQuery.data) return false;
    return (
      JSON.stringify(gridToWindows(grid)) !==
      JSON.stringify(gridToWindows(shiftsToGrid(weekQuery.data.shifts)))
    );
  }, [grid, weekQuery.data]);

  function submitGrid() {
    if (!grid) return;
    const problem = validateGrid(grid);
    if (problem) {
      setGridError(problem);
      return;
    }
    if (grid.length === 0 && !confirmClear) {
      setConfirmClear(true);
      setGridError(
        "Saving an empty grid removes every working hour for this advisor. Press Save again to confirm.",
      );
      return;
    }
    setGridError(null);
    saveGrid.mutate(gridToWindows(grid));
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Availability — ${advisor.full_name}`}
      footer={
        tab === "grid" ? (
          <div className="flex items-center justify-between gap-sp-5">
            <span className="t-caption text-ink-4">
              {grid ? `${weeklyHours(grid)} h per week` : "\u00a0"}
            </span>
            <span className="flex items-center gap-sp-4">
              <Button variant="ghost" onClick={onClose}>
                Close
              </Button>
              <Button
                variant="primary"
                onClick={submitGrid}
                disabled={!grid || !dirty || saveGrid.isPending}
              >
                {saveGrid.isPending ? "Saving…" : "Save schedule"}
              </Button>
            </span>
          </div>
        ) : (
          <div className="flex justify-end">
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        )
      }
    >
      {!advisor.is_on_call ? (
        <Card className="mb-sp-6">
          <p className="t-ui text-ink-1">Not in the escalation rota</p>
          <p className="t-caption mt-sp-2 max-w-[52ch] text-ink-4">
            Coverage only counts advisors with Rota enabled. This schedule is saved and kept, but it
            contributes nothing to the coverage report until Rota is turned on for{" "}
            {advisor.full_name}.
          </p>
        </Card>
      ) : null}

      <Tabs
        items={TABS.map((t) => t.label)}
        active={TABS.find((t) => t.id === tab)!.label}
        onSelect={(label) => setTab(TABS.find((t) => t.label === label)!.id)}
      />

      <div className="mt-sp-6">
        {weekQuery.isPending ? <CardSkeleton /> : null}

        {weekQuery.isError ? (
          <ErrorState error={weekQuery.error} onRetry={() => weekQuery.refetch()} />
        ) : null}

        {weekQuery.data && tab === "grid" && grid ? (
          <GridTab
            grid={grid}
            setGrid={(next) => {
              setGrid(next);
              setGridError(null);
              setConfirmClear(false);
            }}
            timeZone={timeZone}
            error={gridError ?? (saveGrid.isError ? errorMessage(saveGrid.error) : null)}
          />
        ) : null}

        {weekQuery.data && tab === "time-off" ? (
          <TimeOffTab
            rows={weekQuery.data.time_off}
            timeZone={timeZone}
            onCreate={(input) => addTimeOff.mutate(input)}
            onDelete={(id) => removeTimeOff.mutate(id)}
            pending={addTimeOff.isPending}
            error={
              addTimeOff.isError
                ? errorMessage(addTimeOff.error)
                : removeTimeOff.isError
                  ? errorMessage(removeTimeOff.error)
                  : null
            }
          />
        ) : null}
      </div>
    </Modal>
  );
}

function GridTab({
  grid,
  setGrid,
  timeZone,
  error,
}: {
  grid: GridWindow[];
  setGrid: (next: GridWindow[]) => void;
  timeZone: string;
  error: string | null;
}) {
  function update(uid: string, patch: Partial<GridWindow>) {
    setGrid(grid.map((w) => (w.uid === uid ? { ...w, ...patch } : w)));
  }

  return (
    <div>
      <p className="t-caption mb-sp-5 text-ink-4">
        Times are local to {timeZone}. Saving replaces the whole week in one operation.
      </p>

      <div className="flex flex-col gap-sp-5">
        {WEEKDAY_LABELS.map((label, weekday) => {
          const rows = grid.filter((w) => w.weekday === weekday);
          return (
            <div
              key={label}
              className="rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-5"
            >
              <div className="flex items-center justify-between">
                <span className="t-label text-ink-2">{label}</span>
                <IconButton
                  label={`Add a window on ${label}`}
                  icon={Plus}
                  size="sm"
                  onClick={() =>
                    setGrid([
                      ...grid,
                      { uid: newUid(), weekday, start: "09:00", end: "17:00", is_active: true },
                    ])
                  }
                />
              </div>

              {rows.length === 0 ? (
                <p className="t-caption mt-sp-4 text-ink-5">No working hours</p>
              ) : (
                <div className="mt-sp-4 flex flex-col gap-sp-4">
                  {rows.map((row) => (
                    <div key={row.uid} className="flex items-center gap-sp-4">
                      <input
                        type="time"
                        value={row.start}
                        onChange={(e) => update(row.uid, { start: e.target.value })}
                        aria-label={`${label} start`}
                        className="h-[34px] rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
                      />
                      <span className="t-caption text-ink-5">to</span>
                      <input
                        type="time"
                        value={row.end}
                        onChange={(e) => update(row.uid, { end: e.target.value })}
                        aria-label={`${label} end`}
                        className="h-[34px] rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
                      />
                      <Segmented
                        items={["Active", "Paused"]}
                        active={row.is_active ? "Active" : "Paused"}
                        onSelect={(value) => update(row.uid, { is_active: value === "Active" })}
                      />
                      <IconButton
                        label={`Remove this ${label} window`}
                        icon={Trash2}
                        size="sm"
                        onClick={() => setGrid(grid.filter((w) => w.uid !== row.uid))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error ? (
        <div className="mt-sp-5">
          <InlineError error={error} />
        </div>
      ) : null}
    </div>
  );
}

function TimeOffTab({
  rows,
  timeZone,
  onCreate,
  onDelete,
  pending,
  error,
}: {
  rows: { id: string; starts_at: string; ends_at: string; reason: string | null }[];
  timeZone: string;
  onCreate: (input: { starts_at: string; ends_at: string; reason?: string }) => void;
  onDelete: (id: string) => void;
  pending: boolean;
  error: string | null;
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  function submit() {
    if (!start || !end) {
      setLocalError("Both a start and an end are required.");
      return;
    }
    if (end <= start) {
      setLocalError("The end must be after the start.");
      return;
    }
    setLocalError(null);
    onCreate({
      starts_at: businessLocalToIso(start, timeZone),
      ends_at: businessLocalToIso(end, timeZone),
      ...(reason.trim() ? { reason: reason.trim().slice(0, 120) } : {}),
    });
    setStart("");
    setEnd("");
    setReason("");
  }

  return (
    <div>
      <p className="t-caption mb-sp-5 text-ink-4">
        Entered and shown in {timeZone}. Absences that have already ended are not returned by the
        API.
      </p>

      {rows.length === 0 ? (
        <p className="t-caption text-ink-5">No upcoming time off.</p>
      ) : (
        <div className="flex flex-col gap-sp-4">
          {rows.map((row) => (
            <div
              key={row.id}
              className="flex items-center justify-between rounded-r-3 border border-stroke-subtle bg-surface-2 px-sp-5 py-sp-4"
            >
              <span>
                <span className="t-ui block text-ink-1">
                  {formatBusinessInstant(row.starts_at, timeZone)} —{" "}
                  {formatBusinessInstant(row.ends_at, timeZone)}
                </span>
                {row.reason ? (
                  <span className="t-caption block text-ink-4">{row.reason}</span>
                ) : null}
              </span>
              <IconButton
                label="Delete this absence"
                icon={Trash2}
                size="sm"
                onClick={() => onDelete(row.id)}
              />
            </div>
          ))}
        </div>
      )}

      <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-6">
        <p className="t-label mb-sp-4 text-ink-2">Add time off</p>
        <div className="flex flex-col gap-sp-4">
          <label className="flex items-center gap-sp-4">
            <span className="t-caption w-[48px] text-ink-4">From</span>
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="h-[34px] flex-1 rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
          <label className="flex items-center gap-sp-4">
            <span className="t-caption w-[48px] text-ink-4">To</span>
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="h-[34px] flex-1 rounded-r-3 border border-stroke-default bg-surface-3 px-sp-4 t-mono text-ink-1 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
          <TextField
            label="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Optional, 120 characters"
          />
          <div className="flex justify-end">
            <Button variant="secondary" onClick={submit} disabled={pending}>
              {pending ? "Adding…" : "Add time off"}
            </Button>
          </div>
        </div>
        {localError || error ? (
          <div className="mt-sp-4">
            <InlineError error={localError ?? error ?? ""} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
