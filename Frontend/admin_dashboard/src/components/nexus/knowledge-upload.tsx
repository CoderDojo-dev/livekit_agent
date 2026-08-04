import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { Button, TextField } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { uploadDocument } from "@/lib/api/knowledge.server";
import { knowledgeKeys } from "@/lib/nexus/query-keys";
import { uploadOutcome } from "@/lib/nexus/knowledge-view";
import type { UploadResult } from "@/lib/api/knowledge.server";

/** F19 — no file-input primitive exists; a hidden input driven by the existing Button. */
export function KnowledgeUpload({ onOutcome }: { onOutcome?: (o: Outcome) => void }) {
  const [open, setOpen] = useState(false);
  const [documentType, setDocumentType] = useState("general");
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Choose a file first.");
      const base64 = await readAsBase64(file);
      return uploadDocument({
        data: { documentType, fileName: file.name, fileType: file.type, fileBase64: base64 },
      });
    },
    onSuccess: (result: UploadResult) => {
      // F9 — `unchanged` reports neutral copy, not "success"; close in both cases.
      onOutcome?.(uploadOutcome(result));
      void queryClient.invalidateQueries({ queryKey: knowledgeKeys.documents() });
      void queryClient.invalidateQueries({ queryKey: knowledgeKeys.health() });
      setOpen(false);
    },
  });

  function reset() {
    setDocumentType("general");
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <>
      <Button
        icon={Upload}
        size="sm"
        variant="primary"
        className="ml-auto"
        onClick={() => {
          reset();
          setOpen(true);
        }}
      >
        Upload source
      </Button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Upload a source document"
        description="Stored in the corpus and indexed so the agent can retrieve it."
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={mutation.isPending || !file}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Indexing\u2026" : "Upload"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-sp-5">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.csv,.json,.md,.txt"
            className="sr-only"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <div className="flex items-center gap-sp-4">
            <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
              Choose file
            </Button>
            <span className="t-caption truncate text-ink-3">
              {file ? file.name : "No file chosen"}
            </span>
          </div>
          <TextField
            label="Document type"
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
          />
          {mutation.isError ? <InlineError error={mutation.error} /> : null}
        </div>
      </Modal>
    </>
  );
}

export type Outcome = ReturnType<typeof uploadOutcome>;

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") {
        resolve(result.slice(result.indexOf(",") + 1));
      } else {
        reject(new Error("Could not read file"));
      }
    };
    reader.onerror = () => reject(new Error("Could not read file"));
    reader.readAsDataURL(file);
  });
}
