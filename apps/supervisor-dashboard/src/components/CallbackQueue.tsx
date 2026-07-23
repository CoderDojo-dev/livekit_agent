import { useState } from "react";
import {
  Button,
  ContentSwitcher,
  DataTableSkeleton,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
  Tile,
} from "@carbon/react";
import { PhoneFilled } from "@carbon/icons-react";
import { api } from "../api";
import { usePoll, useRefresh } from "../refresh";
import { ErrorBanner, PageHeader } from "./shared";
import type { Callback } from "../types";

/**
 * The callback queue: every promise the agent made when no advisor was free.
 * Until this existed the rows were written and never read, so nobody could say whether a
 * promised call was ever made. Overdue items are surfaced first because those are broken promises.
 */
export function CallbackQueue() {
  const [status, setStatus] = useState<"pending" | "completed" | "cancelled">("pending");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});

  const { sync } = useRefresh();
  const { data, error, loading } = usePoll(
    () => api.callbacks(status, overdueOnly),
    [status, overdueOnly],
  );
  const { data: stats } = usePoll(api.callbackStats, []);

  async function act(id: string, action: "reached" | "no_answer" | "cancel") {
    setBusy(id);
    try {
      if (action === "cancel") {
        await api.cancelCallback(id, note[id] ?? "");
      } else {
        await api.completeCallback(id, note[id] ?? "", action === "reached");
      }
      sync(); // bump the shared poll tick so the table reflects the change
    } finally {
      setBusy(null);
    }
  }

  if (error) {
    return (
      <>
        <PageHeader title="Callback Queue" />
        <ErrorBanner title="Could not load callbacks" error={error} />
      </>
    );
  }

  const rows: Callback[] = data?.callbacks ?? [];

  return (
    <>
      <PageHeader
        title="Callback Queue"
        subtitle="Callbacks promised to callers when no advisor was available"
      />

      {stats && (
        <div className="callback-stats">
          <Tile>
            <p>Pending</p>
            <h3>{stats.pending}</h3>
          </Tile>
          <Tile className={stats.overdue > 0 ? "kpi-tile--danger" : undefined}>
            <p>Overdue</p>
            <h3>{stats.overdue}</h3>
          </Tile>
          <Tile className="kpi-tile--success">
            <p>Completed</p>
            <h3>{stats.completed}</h3>
          </Tile>
        </div>
      )}

      <ContentSwitcher
        onChange={({ name }) => setStatus(name as typeof status)}
        selectedIndex={["pending", "completed", "cancelled"].indexOf(status)}
      >
        <Switch name="pending" text="Pending" />
        <Switch name="completed" text="Completed" />
        <Switch name="cancelled" text="Cancelled" />
      </ContentSwitcher>

      {status === "pending" && (
        <Button
          kind={overdueOnly ? "danger--tertiary" : "tertiary"}
          size="sm"
          onClick={() => setOverdueOnly((v) => !v)}
        >
          {overdueOnly ? "Showing overdue only" : "Show overdue only"}
        </Button>
      )}

      {loading && !data ? (
        <DataTableSkeleton columnCount={6} rowCount={5} />
      ) : (
        <TableContainer title={`${rows.length} callback(s)`}>
          <Table size="lg">
            <TableHead>
              <TableRow>
                <TableHeader>Caller</TableHeader>
                <TableHeader>Requested window</TableHeader>
                <TableHeader>Reason</TableHeader>
                <TableHeader>Attempts</TableHeader>
                <TableHeader>Assigned</TableHeader>
                <TableHeader>Outcome</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <strong>{row.customer_name ?? "Unknown"}</strong>
                    <br />
                    <span className="cds--type-helper-text-01">{row.customer_phone}</span>
                    {row.overdue && (
                      <Tag type="red" size="sm">
                        Overdue
                      </Tag>
                    )}
                  </TableCell>
                  {/* The caller's own words, not a timestamp the system guessed. */}
                  <TableCell>{row.preferred_window ?? "—"}</TableCell>
                  <TableCell>
                    <Tag type="gray" size="sm">
                      {row.reason ?? "—"}
                    </Tag>
                  </TableCell>
                  <TableCell>{row.attempts}</TableCell>
                  <TableCell>{row.assigned_advisor_name ?? "—"}</TableCell>
                  <TableCell>
                    {row.status === "pending" ? (
                      <div className="callback-actions">
                        <TextInput
                          id={`note-${row.id}`}
                          labelText=""
                          placeholder="Outcome note"
                          size="sm"
                          value={note[row.id] ?? ""}
                          onChange={(e) =>
                            setNote((n) => ({ ...n, [row.id]: e.target.value }))
                          }
                        />
                        <Button
                          size="sm"
                          renderIcon={PhoneFilled}
                          disabled={busy === row.id}
                          onClick={() => act(row.id, "reached")}
                        >
                          Reached
                        </Button>
                        <Button
                          size="sm"
                          kind="tertiary"
                          disabled={busy === row.id}
                          onClick={() => act(row.id, "no_answer")}
                        >
                          No answer
                        </Button>
                        <Button
                          size="sm"
                          kind="danger--ghost"
                          disabled={busy === row.id}
                          onClick={() => act(row.id, "cancel")}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      (row.outcome_note ?? "—")
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </>
  );
}
