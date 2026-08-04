import { useEffect, useState } from "react";
import { Button, Checkbox, Segmented, Token } from "@/components/nexus/primitives";
import { TextField } from "@/components/nexus/primitives";
import { InlineError } from "@/components/nexus/states";
import { Modal } from "@/components/nexus/modal";
import { ADVISOR_STATUS_OPTIONS, parseSkills } from "@/lib/nexus/advisor-view";
import type { Advisor, AdvisorStatus } from "@/lib/api/advisors.server";

export type AdvisorFormValues = {
  full_name: string;
  email: string;
  phone_e164: string;
  sip_uri: string;
  skills: string[];
  language: string;
  status: AdvisorStatus;
  max_concurrent_calls: number;
  is_on_call: boolean;
  is_active: boolean;
};

const STATUS_LABELS = ADVISOR_STATUS_OPTIONS.map((o) => o.label);

function labelToStatus(label: string): AdvisorStatus {
  return ADVISOR_STATUS_OPTIONS.find((o) => o.label === label)?.value ?? "offline";
}

function statusToLabel(value: AdvisorStatus): string {
  return ADVISOR_STATUS_OPTIONS.find((o) => o.value === value)?.label ?? "Offline";
}

function toFormValues(advisor: Advisor | null): AdvisorFormValues {
  return {
    full_name: advisor?.full_name ?? "",
    email: advisor?.email ?? "",
    phone_e164: advisor?.phone_e164 ?? "",
    sip_uri: advisor?.sip_uri ?? "",
    skills: advisor?.skills ?? ["general"],
    language: advisor?.language ?? "fr",
    status: advisor?.status ?? "offline",
    max_concurrent_calls: advisor?.max_concurrent_calls ?? 1,
    is_on_call: advisor?.is_on_call ?? false,
    is_active: advisor?.is_active ?? true,
  };
}

export function AdvisorFormModal({
  open,
  advisor,
  pending,
  serverError,
  onClose,
  onSubmit,
}: {
  open: boolean;
  /** null = create mode */
  advisor: Advisor | null;
  pending: boolean;
  serverError: string | null;
  onClose: () => void;
  onSubmit: (values: AdvisorFormValues) => void;
}) {
  const [values, setValues] = useState<AdvisorFormValues>(() => toFormValues(advisor));
  const [skillsText, setSkillsText] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  // Reset whenever the modal opens, or the edited advisor changes.
  useEffect(() => {
    if (!open) return;
    const next = toFormValues(advisor);
    setValues(next);
    setSkillsText(next.skills.join(", "));
    setLocalError(null);
  }, [open, advisor]);

  const isEdit = advisor !== null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLocalError(null);

    const skills = parseSkills(skillsText);
    const payload: AdvisorFormValues = { ...values, skills };

    if (!payload.full_name.trim()) {
      setLocalError("Name is required.");
      return;
    }
    // Mirrors advisors.py: an advisor needs a phone_e164 or a sip_uri.
    if (!payload.phone_e164.trim() && !payload.sip_uri.trim()) {
      setLocalError("An advisor needs a phone number or a SIP URI to be reachable.");
      return;
    }
    if (!Number.isInteger(payload.max_concurrent_calls) || payload.max_concurrent_calls < 1) {
      setLocalError("Capacity must be a whole number of 1 or more.");
      return;
    }

    onSubmit(payload);
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Edit advisor" : "New advisor"}
      description={
        isEdit
          ? "Contact details, skills and capacity. Live call count is managed by the routing engine."
          : "Register an advisor the escalation router can reach."
      }
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="advisor-form" disabled={pending}>
            {pending ? "Saving…" : isEdit ? "Save changes" : "Create advisor"}
          </Button>
        </>
      }
    >
      <form id="advisor-form" onSubmit={handleSubmit} className="flex flex-col gap-sp-6">
        <TextField
          label="Full name"
          value={values.full_name}
          onChange={(event) => setValues((s) => ({ ...s, full_name: event.target.value }))}
          placeholder="Nadia Rahman"
          autoFocus
        />

        <TextField
          label="Email"
          type="email"
          value={values.email}
          onChange={(event) => setValues((s) => ({ ...s, email: event.target.value }))}
          placeholder="nadia@example.com"
        />

        <div className="grid grid-cols-2 gap-sp-5">
          <TextField
            label="Phone (E.164)"
            value={values.phone_e164}
            onChange={(event) => setValues((s) => ({ ...s, phone_e164: event.target.value }))}
            placeholder="+33612345678"
          />
          <TextField
            label="SIP URI"
            value={values.sip_uri}
            onChange={(event) => setValues((s) => ({ ...s, sip_uri: event.target.value }))}
            placeholder="sip:nadia@pbx.local"
          />
        </div>
        <p className="t-caption -mt-sp-3 text-ink-4">
          At least one of phone or SIP is required — it is how the router reaches this advisor.
        </p>

        <TextField
          label="Skills"
          value={skillsText}
          onChange={(event) => setSkillsText(event.target.value)}
          placeholder="general, billing, technique"
        />
        <div className="-mt-sp-3 flex flex-wrap items-center gap-sp-2">
          {parseSkills(skillsText).map((skill) => (
            <Token key={skill} mono={false}>
              {skill}
            </Token>
          ))}
          {parseSkills(skillsText).length === 0 ? (
            <span className="t-caption text-ink-4">Defaults to “general” when left empty.</span>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-sp-5">
          <TextField
            label="Language"
            value={values.language}
            onChange={(event) => setValues((s) => ({ ...s, language: event.target.value }))}
            placeholder="fr"
          />
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-3">Max concurrent calls</span>
            <input
              type="number"
              min={1}
              step={1}
              value={values.max_concurrent_calls}
              onChange={(event) =>
                setValues((s) => ({
                  ...s,
                  max_concurrent_calls: Number(event.target.value),
                }))
              }
              className="h-[34px] w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 t-ui-regular text-ink-1 placeholder:text-ink-4 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink"
            />
          </label>
        </div>

        <div className="flex flex-col gap-sp-3">
          <span className="t-label text-ink-3">Presence</span>
          <Segmented
            items={STATUS_LABELS}
            active={statusToLabel(values.status)}
            onSelect={(label) => setValues((s) => ({ ...s, status: labelToStatus(label) }))}
          />
        </div>

        <div className="flex items-center gap-sp-5">
          <span className="flex items-center gap-sp-3">
            <Checkbox
              label="Escalation rota"
              checked={values.is_on_call}
              onChange={(checked) => setValues((s) => ({ ...s, is_on_call: checked }))}
            />
            <span className="t-ui text-ink-2">Escalation rota</span>
          </span>
          <span className="flex items-center gap-sp-3">
            <Checkbox
              label="Active"
              checked={values.is_active}
              onChange={(checked) => setValues((s) => ({ ...s, is_active: checked }))}
            />
            <span className="t-ui text-ink-2">Active</span>
          </span>
        </div>
        <p className="t-caption -mt-sp-3 text-ink-4">
          Rota advisors receive the dossier when nobody could take the call live.
        </p>

        {localError ? <InlineError error={localError} /> : null}
        {serverError ? <InlineError error={serverError} /> : null}
      </form>
    </Modal>
  );
}

export function DeleteAdvisorModal({
  advisor,
  pending,
  serverError,
  onClose,
  onConfirm,
}: {
  advisor: Advisor | null;
  pending: boolean;
  serverError: string | null;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const onLiveCall = (advisor?.active_calls ?? 0) > 0;

  return (
    <Modal
      open={advisor !== null}
      onClose={onClose}
      title="Delete advisor"
      {...(advisor ? { description: `${advisor.full_name} will be removed permanently.` } : {})}
      footer={
        <>
          <Button onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={pending || onLiveCall}>
            {pending ? "Deleting…" : "Delete permanently"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-sp-5">
        <p className="t-ui-regular text-ink-2">
          This also deletes the advisor’s weekly schedule and every recorded absence. It cannot be
          undone.
        </p>
        <p className="t-caption text-ink-4">
          To remove someone from routing while keeping their history, deactivate them instead.
        </p>
        {onLiveCall ? (
          <InlineError error="This advisor is on a live call. Wait for the call to end before deleting." />
        ) : null}
        {serverError ? <InlineError error={serverError} /> : null}
      </div>
    </Modal>
  );
}
