import { Modal } from "@/components/nexus/modal";
import { StatusChip, Token } from "@/components/nexus/primitives";
import {
  callbackCustomer,
  callbackStatusKey,
  formatBusinessTime,
  priorityLabel,
} from "@/lib/nexus/callback-view";
import type { Callback } from "@/lib/api/callbacks.server";

/** Byte-identical copy of decision-detail.tsx:7-15. Not imported because it is a local there,
 *  and exporting it would add a second export to a component module (lint baseline is fixed). */
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-sp-5 py-sp-4 first:pt-0 last:pb-0">
      <span className="t-label shrink-0 text-ink-3">{label}</span>
      <span className="min-w-0 flex-1 text-right">{children}</span>
    </div>
  );
}

type Props = {
  callback: Callback | null;
  timeZone: string;
  onClose: () => void;
};

/**
 * Read-only lifecycle record for one callback.
 *
 * Every field here already ships from callbacks.py::to_dict() and is already typed in
 * callbacks.server.ts — nothing new is fetched, so there is no loading or error state to
 * render. The modal exists because `outcome_note`, `completed_at` and `session_id` were
 * transported and then thrown away by the table (F15 gap analysis).
 */
export function CallbackLifecycleModal({ callback, timeZone, onClose }: Props) {
  if (!callback) return null;

  const customer = callbackCustomer(callback);
  const priority = priorityLabel(callback.priority_level);
  // cancel_callback() writes its reason into the SAME outcome_note column, so the label
  // must follow the status or a cancellation reason would be mislabelled as an outcome.
  const noteLabel = callback.status === "cancelled" ? "Cancellation reason" : "Outcome note";

  return (
    <Modal
      open
      onClose={onClose}
      title="Callback record"
      description={`${customer.name} \u00b7 ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
    >
      {/* Header strip — same construction as customer-detail.tsx */}
      <div className="flex flex-wrap items-center gap-sp-5 border-b border-stroke-subtle pb-sp-5">
        <StatusChip status={callbackStatusKey(callback)} />
        {priority ? <Token strong>{priority}</Token> : null}
        <Token>
          {callback.attempts} attempt{callback.attempts === 1 ? "" : "s"}
        </Token>
        <span className="t-caption ml-auto text-ink-4">{customer.phone}</span>
      </div>

      <div className="mt-sp-6 flex flex-col divide-y divide-stroke-subtle">
        <Row label="Scheduled">
          <span className="t-mono text-ink-1">
            {formatBusinessTime(callback.scheduled_time, timeZone)}
          </span>
        </Row>

        <Row label="Completed">
          {callback.completed_at ? (
            <span className="t-mono text-ink-1">
              {formatBusinessTime(callback.completed_at, timeZone)}
            </span>
          ) : (
            <span className="t-caption text-ink-5">
              {callback.status === "pending" ? "Still pending" : "Never completed"}
            </span>
          )}
        </Row>

        <Row label="Preferred window">
          {callback.preferred_window ? (
            <Token>{callback.preferred_window}</Token>
          ) : (
            <span className="t-caption text-ink-5">{"\u2014"}</span>
          )}
        </Row>

        <Row label="Reason">
          {callback.reason ? (
            <p className="t-ui text-left text-ink-2">{callback.reason}</p>
          ) : (
            <span className="t-caption text-ink-5">{"\u2014"}</span>
          )}
        </Row>

        <Row label="Advisor">
          {callback.assigned_advisor_name ? (
            <span className="t-ui text-ink-1">{callback.assigned_advisor_name}</span>
          ) : (
            <span className="t-caption text-ink-5">Unassigned</span>
          )}
        </Row>

        <Row label={noteLabel}>
          {callback.outcome_note ? (
            <p className="t-ui text-left text-ink-2">{callback.outcome_note}</p>
          ) : (
            <span className="t-caption text-ink-5">No note recorded.</span>
          )}
        </Row>

        <Row label="Originating call">
          {callback.session_id ? (
            <a
              className="t-mono break-all text-ink-1 underline decoration-dotted decoration-from-font underline-offset-4 hover:text-ink-4"
              href={`/calls?session=${encodeURIComponent(callback.session_id)}`}
            >
              {callback.session_id}
            </a>
          ) : (
            <span className="t-caption text-ink-5">Not linked to a session</span>
          )}
        </Row>

        <Row label="Callback ID">
          <span className="t-mono break-all text-ink-2">{callback.id}</span>
        </Row>
      </div>

      {callback.attempts === 0 ? (
        <p className="t-caption mt-sp-6 text-ink-5">
          Attempts are counted when an advisor claims a callback from the queue, so one handled
          directly from this table can close with none recorded.
        </p>
      ) : null}
    </Modal>
  );
}
