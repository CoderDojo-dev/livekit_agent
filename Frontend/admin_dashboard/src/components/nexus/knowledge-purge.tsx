import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { Button, IconButton, TextField } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { purgeDocument } from "@/lib/api/knowledge.server";
import { knowledgeKeys } from "@/lib/nexus/query-keys";

/**
 * F8 — purge is genuinely destructive (archives rows, deactivates chunks, deletes Qdrant points,
 * AND removes the object from MinIO). There is no destructive button variant in the design system,
 * so the friction lives in a typed confirmation: the user must type the exact `source` before the
 * confirm button enables. We always send remove_object=true (the default): a file left in the
 * bucket is re-ingested as a new version on the next scan.
 */
export function KnowledgePurge({ source }: { source: string }) {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      purgeDocument({
        data: { source },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: knowledgeKeys.documents() });
      void queryClient.invalidateQueries({ queryKey: knowledgeKeys.health() });
      setOpen(false);
      setConfirmation("");
    },
  });

  return (
    <>
      <IconButton label="Purge source" icon={Trash2} size="sm" onClick={() => setOpen(true)} />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Purge this source?"
        description="This removes the document from the index, the records, and the storage bucket. It cannot be recovered."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={confirmation !== source || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Purging\u2026" : "Purge permanently"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-sp-5">
          <p className="t-caption text-ink-4">
            Type the exact source to confirm:
            <span className="t-mono ml-sp-2 text-ink-2">{source}</span>
          </p>
          <TextField
            label="Source"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder={source}
          />
          {mutation.isError ? <InlineError error={mutation.error} /> : null}
        </div>
      </Modal>
    </>
  );
}
