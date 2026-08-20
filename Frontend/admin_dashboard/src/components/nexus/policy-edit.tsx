import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Lock, Plus, Trash2 } from "lucide-react";
import { Button, IconButton, TextField, Token } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { SettingToggle } from "@/components/nexus/setting-row";
import { createPolicyRule, deletePolicyRule, updatePolicyRule } from "@/lib/api/policies.server";
import { policyKeys } from "@/lib/nexus/query-keys";
import type { PolicyRule } from "@/lib/api/policies.server";

/**
 * Policy registry editing.
 *
 * WHAT THESE CONTROLS CAN AND CANNOT DO — the reason it is safe to offer them at all.
 *
 * `reference.business_rules` is a governance record. Its only readers are this console and the
 * seed script; policy-service, decision-service and agent-worker never query it — they read
 * POLICY_* environment variables. So nothing edited here can change what the agent enforces.
 *
 * Consequently there is NO threshold field anywhere below. The numbers shown against a governed
 * rule are overlaid from the live environment at read time, and offering an input for them would
 * let the registry advertise a limit the engine is not applying.
 *
 * business-api refuses to deactivate or delete a governed rule. Rather than hide those controls
 * and leave the reason a mystery, they are shown DISABLED with the reason stated — and the
 * server's own refusal is surfaced verbatim if one is ever attempted anyway.
 */

function useInvalidatePolicies() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: policyKeys.all });
}

/* ---------------------------------------------------------------------------------------------
 * Edit
 * ------------------------------------------------------------------------------------------- */

export function PolicyEditDialog({ rule, onClose }: { rule: PolicyRule; onClose: () => void }) {
  const invalidate = useInvalidatePolicies();
  const [description, setDescription] = useState(rule.description ?? "");
  const [active, setActive] = useState(rule.active);

  const save = useMutation({
    mutationFn: () =>
      updatePolicyRule({
        data: {
          ruleId: rule.rule_id,
          ...(description === (rule.description ?? "") ? {} : { description }),
          ...(active === rule.active ? {} : { active }),
        },
      }),
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });

  const changed = description !== (rule.description ?? "") || active !== rule.active;

  return (
    <Modal
      open
      onClose={onClose}
      title="Edit policy rule"
      description={`${rule.rule_id} · ${rule.domain}`}
      className="max-w-[560px]"
      footer={
        <>
          <Button onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => save.mutate()}
            disabled={!changed || save.isPending}
          >
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </>
      }
    >
      <div className="space-y-sp-7">
        <div>
          <label htmlFor="policy-description" className="t-micro mb-sp-4 block text-ink-5">
            Description
          </label>
          <textarea
            id="policy-description"
            rows={4}
            maxLength={4000}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What this rule governs, and why it exists."
            className="w-full resize-y rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 placeholder:text-ink-5 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-sp-5 border-t border-stroke-subtle pt-sp-6">
          <div className="min-w-0">
            <p className="t-body-strong text-ink-1">Active</p>
            <p className="t-caption mt-sp-2 max-w-[52ch] text-ink-4">
              {rule.enforced
                ? "This rule is enforced from the environment and cannot be deactivated here."
                : "Inactive rules stay in the registry as history and are marked accordingly."}
            </p>
          </div>
          {rule.enforced ? (
            <Token strong>
              <Lock size={11} strokeWidth={1.5} aria-hidden="true" />
              Enforced
            </Token>
          ) : (
            <SettingToggle name="Active" value={active} onChange={setActive} />
          )}
        </div>

        {/* Thresholds are shown, never edited — see the module note. */}
        {rule.enforced ? (
          <div className="border-t border-stroke-subtle pt-sp-6">
            <p className="t-micro mb-sp-3 text-ink-5">Thresholds</p>
            <p className="t-caption max-w-[60ch] text-ink-4">
              Read live from{" "}
              {(rule.governed_by ?? []).map((variable) => (
                <Token key={variable} className="mx-sp-1">
                  {variable}
                </Token>
              ))}{" "}
              and applied by the policy engine. They are not stored in this registry, so they cannot
              be edited from the console — change the environment variable and restart
              policy-service.
            </p>
          </div>
        ) : null}

        {save.isError ? <InlineError error={save.error} /> : null}
      </div>
    </Modal>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Create
 * ------------------------------------------------------------------------------------------- */

export function PolicyCreateButton() {
  const [open, setOpen] = useState(false);
  const invalidate = useInvalidatePolicies();

  const [ruleId, setRuleId] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");

  const create = useMutation({
    mutationFn: () =>
      createPolicyRule({
        data: {
          ruleId: ruleId.trim(),
          domain: domain.trim() || "general",
          ...(description.trim() ? { description: description.trim() } : {}),
        },
      }),
    onSuccess: async () => {
      await invalidate();
      setRuleId("");
      setDomain("");
      setDescription("");
      setOpen(false);
    },
  });

  return (
    <>
      <Button icon={Plus} onClick={() => setOpen(true)}>
        New rule
      </Button>

      {open ? (
        <Modal
          open
          onClose={() => setOpen(false)}
          title="New policy rule"
          description="A governance record. Thresholds stay in the environment."
          className="max-w-[560px]"
          footer={
            <>
              <Button onClick={() => setOpen(false)} disabled={create.isPending}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() => create.mutate()}
                disabled={!ruleId.trim() || create.isPending}
              >
                {create.isPending ? "Creating…" : "Create rule"}
              </Button>
            </>
          }
        >
          <div className="space-y-sp-6">
            <TextField
              label="Rule id"
              placeholder="RULE_REFUND_WINDOW"
              value={ruleId}
              onChange={(event) => setRuleId(event.target.value.toUpperCase())}
            />
            <TextField
              label="Domain"
              placeholder="billing"
              value={domain}
              onChange={(event) => setDomain(event.target.value)}
            />
            <div>
              <label htmlFor="new-policy-description" className="t-micro mb-sp-3 block text-ink-5">
                Description
              </label>
              <textarea
                id="new-policy-description"
                rows={3}
                maxLength={4000}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                className="w-full resize-y rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 placeholder:text-ink-5 transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none"
              />
            </div>

            <p className="t-caption flex items-start gap-sp-3 text-ink-4">
              <AlertTriangle size={13} strokeWidth={1.5} className="mt-[2px] shrink-0" />
              <span>
                This records intent for review. It does not add a runtime check — the agent is
                governed by the policy engine, not by this registry.
              </span>
            </p>

            {create.isError ? <InlineError error={create.error} /> : null}
          </div>
        </Modal>
      ) : null}
    </>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Delete
 * ------------------------------------------------------------------------------------------- */

export function PolicyDeleteButton({ rule }: { rule: PolicyRule }) {
  const [open, setOpen] = useState(false);
  const invalidate = useInvalidatePolicies();

  const remove = useMutation({
    mutationFn: () => deletePolicyRule({ data: { ruleId: rule.rule_id } }),
    onSuccess: async () => {
      await invalidate();
      setOpen(false);
    },
  });

  // Governed rules document a live guardrail; the server refuses to delete them, so the control
  // is disabled here with the reason rather than failing after the click.
  const locked = rule.enforced;

  return (
    <>
      <IconButton
        size="sm"
        label={
          locked ? `${rule.rule_id} is enforced and cannot be deleted` : `Delete ${rule.rule_id}`
        }
        icon={locked ? Lock : Trash2}
        disabled={locked}
        onClick={() => setOpen(true)}
      />

      {open && !locked ? (
        <Modal
          open
          onClose={() => setOpen(false)}
          title="Delete policy rule"
          description={rule.rule_id}
          footer={
            <>
              <Button onClick={() => setOpen(false)} disabled={remove.isPending}>
                Cancel
              </Button>
              <Button variant="primary" onClick={() => remove.mutate()} disabled={remove.isPending}>
                {remove.isPending ? "Deleting…" : "Delete rule"}
              </Button>
            </>
          }
        >
          <div className="flex items-start gap-sp-5">
            <AlertTriangle size={16} strokeWidth={1.5} className="mt-sp-2 shrink-0 text-ink-3" />
            <p className="t-ui text-ink-1">
              This removes the governance record for {rule.rule_id}. The agent's behaviour does not
              change — this registry is documentation, not a runtime input. The deletion is written
              to the audit ledger.
            </p>
          </div>

          {remove.isError ? (
            <div className="mt-sp-6">
              <InlineError error={remove.error} />
            </div>
          ) : null}
        </Modal>
      ) : null}
    </>
  );
}
