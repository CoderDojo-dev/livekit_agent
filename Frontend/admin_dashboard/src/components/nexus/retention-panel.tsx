import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { Card, CardHeader, Button, TextField, Token } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { runRetention, type RetentionReport } from "@/lib/api/audit.server";
import { blastRadius, formatInstant } from "@/lib/nexus/audit-view";

export function RetentionPanel() {
  const [days, setDays] = useState("90");
  const [preview, setPreview] = useState<RetentionReport | null>(null);
  const [previewedDays, setPreviewedDays] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<RetentionReport | null>(null);

  // Any change to the window invalidates the dry run and re-locks the purge.
  function changeDays(next: string) {
    setDays(next);
    setPreview(null);
    setPreviewedDays(null);
    setResult(null);
  }

  const dryRun = useMutation({
    mutationFn: () => runRetention({ data: { retentionDays: Number(days), dryRun: true } }),
    onSuccess: (report) => {
      setPreview(report);
      setPreviewedDays(days);
      setResult(null);
    },
  });

  const purge = useMutation({
    mutationFn: () => runRetention({ data: { retentionDays: Number(days), dryRun: false } }),
    onSuccess: (report) => {
      setResult(report);
      setPreview(null);
      setPreviewedDays(null);
      setConfirmOpen(false);
      setTyped("");
    },
  });

  const previewValid = preview !== null && previewedDays === days;
  const expected = String(preview?.sessions_matched ?? "");
  const canPurge = previewValid && preview.sessions_matched > 0;

  return (
    <Card>
      <CardHeader
        title="Data Retention"
        subtitle="Anonymize transcripts and delete audio recordings older than the retention window."
      />

      <div className="mt-sp-6 flex items-end gap-sp-5">
        <TextField
          label="Retention window (days)"
          value={days}
          onChange={(e) => changeDays(e.target.value)}
          inputMode="numeric"
        />
        <Button onClick={() => dryRun.mutate()} disabled={dryRun.isPending}>
          {dryRun.isPending ? "Checking..." : "Preview"}
        </Button>
        <Button onClick={() => setConfirmOpen(true)} disabled={!canPurge || purge.isPending}>
          Purge permanently
        </Button>
      </div>

      {dryRun.isError ? (
        <div className="mt-sp-5">
          <InlineError error={dryRun.error} />
        </div>
      ) : null}
      {purge.isError ? (
        <div className="mt-sp-5">
          <InlineError error={purge.error} />
        </div>
      ) : null}

      {previewValid ? (
        <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-ui text-ink-1">{blastRadius(preview.sessions_matched, preview.cutoff)}</p>
          <p className="t-caption mt-sp-3 text-ink-4">
            Preview only. The number of transcript turns affected is not reported until the purge
            runs.
          </p>
        </div>
      ) : null}

      {result ? (
        <div className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-ui text-ink-1">
            Purge complete. {result.sessions_matched.toLocaleString("en-US")} session(s) processed,{" "}
            {result.turns_anonymized.toLocaleString("en-US")} transcript turn(s) anonymized.
          </p>
          <p className="t-caption mt-sp-3 text-ink-4">
            Cutoff {formatInstant(result.cutoff)}. Audio deletion failures are not reported by the
            job.
          </p>
        </div>
      ) : null}

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm permanent purge"
      >
        <div className="flex items-start gap-sp-5">
          <AlertTriangle
            size={16}
            strokeWidth={1.5}
            aria-hidden="true"
            className="mt-sp-2 text-ink-3"
          />
          <p className="t-ui text-ink-1">
            {preview ? blastRadius(preview.sessions_matched, preview.cutoff) : ""}
          </p>
        </div>
        <p className="t-caption mt-sp-5 text-ink-4">
          Type <Token>{expected}</Token> to confirm.
        </p>
        <div className="mt-sp-5">
          <TextField
            label="Session count"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            inputMode="numeric"
          />
        </div>
        <div className="mt-sp-6 flex justify-end gap-sp-5">
          <Button onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button
            onClick={() => purge.mutate()}
            disabled={typed.trim() !== expected || purge.isPending}
          >
            {purge.isPending ? "Purging..." : "Purge permanently"}
          </Button>
        </div>
      </Modal>
    </Card>
  );
}
