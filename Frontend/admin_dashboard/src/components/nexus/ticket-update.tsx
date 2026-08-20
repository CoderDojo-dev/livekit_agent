import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquareText, PencilLine } from "lucide-react";
import { Button, IconButton, StatusChip, Token } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { adminUpdateTicket, TICKET_ADMIN_STATUSES } from "@/lib/api/tickets.server";
import { ticketKeys, navKeys } from "@/lib/nexus/query-keys";
import { STATUS_LABELS, ticketStatusKey } from "@/lib/nexus/ticket-view";
import { cn } from "@/lib/utils";

/**
 * Manual ticket update: move the state, and leave a note the agent will read to the customer.
 *
 * The row keeps the shape it always had — this adds one icon button, and everything else happens
 * in a dialog. That is deliberate: a table is for reading, and putting editable controls inline
 * would make every row look like a form.
 *
 * WHAT HAPPENS ON SAVE
 * business-api forwards to ticketing-glpi, which writes GLPI first and the local mirror second.
 * If GLPI refuses, nothing is written anywhere and the error is shown here verbatim — the dialog
 * never reports a success the upstream did not accept.
 *
 * The note is stored on the mirror row, which is what the agent's get_ticket_status and
 * lookup_tickets tools return, so it reaches the caller with no agent-side change.
 */
export function TicketUpdateButton({
  ticketId,
  currentStatus,
  currentNote,
  subject,
}: {
  ticketId: string;
  currentStatus: string | null;
  currentNote: string | null;
  subject: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <IconButton
        size="sm"
        label={`Update ticket ${ticketId}`}
        icon={PencilLine}
        onClick={() => setOpen(true)}
      />
      {open ? (
        <TicketUpdateDialog
          ticketId={ticketId}
          currentStatus={currentStatus}
          currentNote={currentNote}
          subject={subject}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function TicketUpdateDialog({
  ticketId,
  currentStatus,
  currentNote,
  subject,
  onClose,
}: {
  ticketId: string;
  currentStatus: string | null;
  currentNote: string | null;
  subject: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(ticketStatusKey(currentStatus));
  const [note, setNote] = useState(currentNote ?? "");

  /* Re-seed if the row updates underneath an open dialog (a background refetch can land). */
  useEffect(() => {
    setStatus(ticketStatusKey(currentStatus));
    setNote(currentNote ?? "");
  }, [currentStatus, currentNote]);

  const save = useMutation({
    mutationFn: () =>
      adminUpdateTicket({
        data: {
          ticketId,
          ...(status === ticketStatusKey(currentStatus)
            ? {}
            : { status: status as (typeof TICKET_ADMIN_STATUSES)[number] }),
          // Send the note only when it actually changed, so a status-only edit does not
          // needlessly rewrite the note's author and timestamp.
          ...(note === (currentNote ?? "") ? {} : { note }),
        },
      }),
    onSuccess: async () => {
      // Every ticket list view is keyed by its filters, so invalidate the whole family. The nav
      // badge counts open tickets and can change with the status, so it is refreshed too.
      await queryClient.invalidateQueries({ queryKey: ticketKeys.all });
      await queryClient.invalidateQueries({ queryKey: navKeys.counts() });
      onClose();
    },
  });

  const statusChanged = status !== ticketStatusKey(currentStatus);
  const noteChanged = note !== (currentNote ?? "");
  const nothingToSave = !statusChanged && !noteChanged;

  return (
    <Modal
      open
      onClose={onClose}
      title="Update ticket"
      description={`${ticketId} · ${subject}`}
      className="max-w-[560px]"
      footer={
        <>
          <Button onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => save.mutate()}
            disabled={nothingToSave || save.isPending}
          >
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </>
      }
    >
      <div className="space-y-sp-7">
        {/* ---- Status ---- */}
        <div>
          <p className="t-micro mb-sp-4 text-ink-5">Status</p>
          <div className="flex flex-wrap gap-sp-3">
            {TICKET_ADMIN_STATUSES.map((option) => {
              const selected = status === option;
              return (
                <button
                  key={option}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setStatus(option)}
                  className={cn(
                    "rounded-r-2 border px-sp-4 py-sp-3 transition-colors duration-[120ms]",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    selected
                      ? "border-stroke-ink bg-surface-3"
                      : "border-stroke-default hover:border-stroke-strong hover:bg-surface-3/60",
                  )}
                >
                  <StatusChip status={option} />
                </button>
              );
            })}
          </div>
          {statusChanged ? (
            <p className="t-caption mt-sp-4 text-ink-4">
              {STATUS_LABELS[ticketStatusKey(currentStatus)] ?? currentStatus} →{" "}
              <span className="text-ink-1">{STATUS_LABELS[status] ?? status}</span>. This is written
              to GLPI first, then mirrored locally.
            </p>
          ) : null}
        </div>

        {/* ---- Note ---- */}
        <div>
          <label htmlFor="ticket-admin-note" className="t-micro mb-sp-4 block text-ink-5">
            Note for the customer
          </label>
          <textarea
            id="ticket-admin-note"
            rows={4}
            maxLength={2000}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="e.g. Fibre splice repaired in your area. Service restored on 20 August."
            className="w-full resize-y rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 placeholder:text-ink-5 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
          />
          <p className="t-caption mt-sp-3 flex items-start gap-sp-3 text-ink-4">
            <MessageSquareText size={13} strokeWidth={1.5} className="mt-[2px] shrink-0" />
            <span>
              The voice agent reads this back when the customer next asks about this ticket. Write
              it as you would say it. Clearing the box removes the note.
            </span>
          </p>
          <p className="t-caption mt-sp-2 text-right text-ink-5">{note.length}/2000</p>
        </div>

        {save.isError ? <InlineError error={save.error} /> : null}
      </div>
    </Modal>
  );
}

/** Row indicator: shows that a ticket carries an admin note, with the text on hover. */
export function TicketNoteMarker({ note }: { note: string | null | undefined }) {
  if (!note) return null;
  return (
    <Token className="shrink-0" title={note}>
      <MessageSquareText size={11} strokeWidth={1.5} aria-hidden="true" />
      <span className="sr-only">Has an administrator note: {note}</span>
    </Token>
  );
}
