import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Modal } from "./modal";
import { Button, Token } from "./primitives";
import { InlineError } from "./states";
import { callbackKeys } from "@/lib/nexus/query-keys";
import { formatBusinessTime } from "@/lib/nexus/callback-view";
import { cancelCallback, completeCallback, type Callback } from "@/lib/api/callbacks.server";

type Props = {
  callback: Callback;
  timeZone: string;
  onClose: () => void;
};

/**
 * Record the outcome of an attempted callback.
 *
 * Two outcomes, deliberately worded differently, because the backend does two different things:
 *   reached=true  -> closed
 *   reached=false -> stays pending, returns to the queue unassigned
 */
export function CallbackOutcomeModal({ callback, timeZone, onClose }: Props) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: (reached: boolean) =>
      completeCallback({ data: { callbackId: callback.id, note, reached } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: callbackKeys.all });
      await queryClient.invalidateQueries({ queryKey: callbackKeys.stats() });
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Record outcome"
      description={`${callback.customer_name ?? "Unknown caller"} · ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
      footer={
        <div className="flex items-center justify-between gap-sp-5">
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Close
          </Button>
          <div className="flex items-center gap-sp-4">
            <Button
              variant="secondary"
              onClick={() => mutation.mutate(false)}
              disabled={mutation.isPending}
            >
              No answer — return to queue
            </Button>
            <Button
              variant="primary"
              onClick={() => mutation.mutate(true)}
              disabled={mutation.isPending}
            >
              Reached — close callback
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-sp-6">
        {callback.attempts > 0 ? (
          <div className="flex items-center gap-sp-3">
            <Token>
              {callback.attempts} attempt{callback.attempts === 1 ? "" : "s"}
            </Token>
            <span className="t-caption text-ink-4">already recorded on this callback.</span>
          </div>
        ) : null}

        <label className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Outcome note</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value.slice(0, 500))}
            maxLength={500}
            rows={4}
            className="w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            placeholder="What happened on this call?"
          />
          <span className="t-caption text-ink-5">
            {note.length > 450 ? `${500 - note.length} characters left. ` : ""}
            Leaving this blank keeps any note already on the callback.
          </span>
        </label>

        <p className="t-caption text-ink-4">
          “No answer” keeps the callback pending and releases the assigned advisor, so it returns to
          the queue for another attempt.
        </p>

        {mutation.isError ? <InlineError error={mutation.error} /> : null}
      </div>
    </Modal>
  );
}

/** Cancelling is terminal and is a supervisor action (superviseur on the route). */
export function CallbackCancelModal({ callback, timeZone, onClose }: Props) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const mutation = useMutation({
    mutationFn: () => cancelCallback({ data: { callbackId: callback.id, note } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: callbackKeys.all });
      await queryClient.invalidateQueries({ queryKey: callbackKeys.stats() });
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Cancel callback"
      description={`${callback.customer_name ?? "Unknown caller"} · ${formatBusinessTime(
        callback.scheduled_time,
        timeZone,
      )}`}
      footer={
        <div className="flex items-center justify-between gap-sp-5">
          <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Keep it
          </Button>
          <Button variant="primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            Cancel callback
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-sp-6">
        <p className="t-body text-ink-2">
          This closes the promise made to the caller. It cannot be undone — there is no way to move
          a cancelled callback back to pending.
        </p>
        <label className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Reason (optional)</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value.slice(0, 500))}
            maxLength={500}
            rows={3}
            className="w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            placeholder="Why is this callback no longer needed?"
          />
        </label>
        {mutation.isError ? <InlineError error={mutation.error} /> : null}
      </div>
    </Modal>
  );
}
