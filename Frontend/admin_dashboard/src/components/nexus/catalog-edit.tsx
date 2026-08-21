import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, SquarePen, Trash2 } from "lucide-react";
import { Button, IconButton, TextField, Token } from "@/components/nexus/primitives";
import { Modal } from "@/components/nexus/modal";
import { InlineError } from "@/components/nexus/states";
import { SettingToggle } from "@/components/nexus/setting-row";
import {
  createGeoArea,
  createProduct,
  createRecharge,
  deleteGeoArea,
  deleteProduct,
  deleteRecharge,
  updateGeoArea,
  updateProduct,
  updateRecharge,
  type AreaEntry,
  type CatalogKind,
  type ProductEntry,
  type RechargeEntry,
} from "@/lib/api/reference.server";
import { referenceKeys } from "@/lib/nexus/query-keys";
import { cn } from "@/lib/utils";

/**
 * Editing for the three catalogs the agent reads at runtime.
 *
 * These are NOT the policy registry. Plans, recharges and geo areas are live inputs: the agent
 * offers a plan, quotes a recharge and resolves a caller's town against these tables while the
 * call is in progress. An edit here is audible on the next call, which is the reason to expose it
 * and the reason each control states what it will affect.
 *
 * Deletion is the dangerous verb, so the backend refuses it wherever something still depends on
 * the row (a plan a subscription points at, an area with children or outages). Those refusals are
 * shown verbatim rather than pre-empted with a guess, because the backend is the only place that
 * can actually count the dependants.
 */

function useInvalidateCatalog() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: referenceKeys.all });
}

const FIELD_CLASS =
  "w-full rounded-r-3 border border-stroke-default bg-surface-3 px-sp-5 py-sp-4 t-body text-ink-1 " +
  "transition-colors duration-[120ms] hover:border-stroke-strong focus:border-stroke-ink focus:outline-none";

/* ---------------------------------------------------------------------------------------------
 * Create — one button, shaped by which catalog is on screen
 * ------------------------------------------------------------------------------------------- */

export function CatalogCreateButton({ catalog }: { catalog: CatalogKind }) {
  const [open, setOpen] = useState(false);
  const invalidate = useInvalidateCatalog();

  // Error messages are managed upstream in GLPI/seed and have no write endpoint here.
  if (catalog === "errors") return null;

  const label =
    catalog === "products" ? "New plan" : catalog === "recharges" ? "New recharge" : "New area";

  return (
    <>
      <Button icon={Plus} onClick={() => setOpen(true)}>
        {label}
      </Button>
      {open ? (
        <CreateDialog
          catalog={catalog}
          onClose={() => setOpen(false)}
          onSaved={() => void invalidate()}
        />
      ) : null}
    </>
  );
}

function CreateDialog({
  catalog,
  onClose,
  onSaved,
}: {
  catalog: CatalogKind;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [planType, setPlanType] = useState<"PREPAID" | "POSTPAID">("PREPAID");
  const [amount, setAmount] = useState("");
  const [bonus, setBonus] = useState("0");
  const [areaType, setAreaType] = useState<"governorate" | "delegation" | "locality">("locality");
  const [parent, setParent] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      if (catalog === "products") {
        return createProduct({
          data: { productCode: code.trim().toUpperCase(), name: name.trim(), planType },
        });
      }
      if (catalog === "recharges") {
        return createRecharge({
          data: {
            code: code.trim().toUpperCase(),
            amount: Number(amount),
            bonusAmount: Number(bonus || 0),
          },
        });
      }
      return createGeoArea({
        data: {
          areaCode: code.trim().toUpperCase(),
          nameFr: name.trim(),
          areaType,
          ...(parent.trim() ? { parentCode: parent.trim().toUpperCase() } : {}),
        },
      });
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  const valid =
    code.trim().length > 0 &&
    (catalog === "recharges" ? Number(amount) > 0 : name.trim().length > 0);

  return (
    <Modal
      open
      onClose={onClose}
      title={
        catalog === "products" ? "New plan" : catalog === "recharges" ? "New recharge" : "New area"
      }
      description="The agent can use this from its next call."
      className="max-w-[560px]"
      footer={
        <>
          <Button onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => create.mutate()}
            disabled={!valid || create.isPending}
          >
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <div className="space-y-sp-6">
        <TextField
          label={catalog === "areas" ? "Area code" : "Code"}
          placeholder={catalog === "areas" ? "TN-11-01" : "PLAN_SMART_20"}
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase())}
        />

        {catalog !== "recharges" ? (
          <TextField
            label={catalog === "areas" ? "Name (French)" : "Name"}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        ) : null}

        {catalog === "products" ? (
          <div>
            <p className="t-micro mb-sp-3 text-ink-5">Plan type</p>
            <div className="flex gap-sp-3">
              {(["PREPAID", "POSTPAID"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  aria-pressed={planType === option}
                  onClick={() => setPlanType(option)}
                  className={cn(
                    "rounded-r-2 border px-sp-5 py-sp-3 t-label transition-colors duration-[120ms]",
                    planType === option
                      ? "border-stroke-ink bg-surface-3 text-ink-1"
                      : "border-stroke-default text-ink-4 hover:text-ink-2",
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {catalog === "recharges" ? (
          <div className="grid gap-sp-5 sm:grid-cols-2">
            <div>
              <label htmlFor="recharge-amount" className="t-micro mb-sp-3 block text-ink-5">
                Amount (TND)
              </label>
              <input
                id="recharge-amount"
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
            <div>
              <label htmlFor="recharge-bonus" className="t-micro mb-sp-3 block text-ink-5">
                Bonus (TND)
              </label>
              <input
                id="recharge-bonus"
                type="number"
                min="0"
                step="0.01"
                value={bonus}
                onChange={(event) => setBonus(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
          </div>
        ) : null}

        {catalog === "areas" ? (
          <>
            <div>
              <p className="t-micro mb-sp-3 text-ink-5">Area type</p>
              <div className="flex flex-wrap gap-sp-3">
                {(["governorate", "delegation", "locality"] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={areaType === option}
                    onClick={() => setAreaType(option)}
                    className={cn(
                      "rounded-r-2 border px-sp-5 py-sp-3 t-label capitalize transition-colors duration-[120ms]",
                      areaType === option
                        ? "border-stroke-ink bg-surface-3 text-ink-1"
                        : "border-stroke-default text-ink-4 hover:text-ink-2",
                    )}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
            <TextField
              label="Parent area code (optional)"
              placeholder="TN-11"
              value={parent}
              onChange={(event) => setParent(event.target.value.toUpperCase())}
            />
            <p className="t-caption flex items-start gap-sp-3 text-ink-4">
              <AlertTriangle size={13} strokeWidth={1.5} className="mt-[2px] shrink-0" />
              <span>
                The parent chain is how the agent decides that an outage on a governorate affects a
                caller in one of its towns. Set it whenever the area sits under another.
              </span>
            </p>
          </>
        ) : null}

        {create.isError ? <InlineError error={create.error} /> : null}
      </div>
    </Modal>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Row actions
 * ------------------------------------------------------------------------------------------- */

export function CatalogRowActions({
  catalog,
  product,
  recharge,
  area,
}: {
  catalog: CatalogKind;
  product?: ProductEntry;
  recharge?: RechargeEntry;
  area?: AreaEntry;
}) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const identifier = product?.product_code ?? recharge?.code ?? area?.area_code ?? "";

  return (
    <span className="inline-flex items-center gap-sp-2 opacity-0 transition-opacity duration-[120ms] group-hover/row:opacity-100 focus-within:opacity-100">
      <IconButton
        size="sm"
        label={`Edit ${identifier}`}
        icon={SquarePen}
        onClick={() => setEditing(true)}
      />
      <IconButton
        size="sm"
        label={`Delete ${identifier}`}
        icon={Trash2}
        onClick={() => setDeleting(true)}
      />

      {editing ? (
        <EditDialog
          catalog={catalog}
          {...(product ? { product } : {})}
          {...(recharge ? { recharge } : {})}
          {...(area ? { area } : {})}
          onClose={() => setEditing(false)}
        />
      ) : null}
      {deleting ? (
        <DeleteDialog
          catalog={catalog}
          identifier={identifier}
          onClose={() => setDeleting(false)}
        />
      ) : null}
    </span>
  );
}

function EditDialog({
  catalog,
  product,
  recharge,
  area,
  onClose,
}: {
  catalog: CatalogKind;
  product?: ProductEntry;
  recharge?: RechargeEntry;
  area?: AreaEntry;
  onClose: () => void;
}) {
  const invalidate = useInvalidateCatalog();

  const [name, setName] = useState(product?.name ?? area?.name_fr ?? "");
  const [active, setActive] = useState(product?.active ?? area?.active ?? true);
  const [amount, setAmount] = useState(String(recharge?.amount ?? ""));
  const [bonus, setBonus] = useState(String(recharge?.bonus_amount ?? "0"));

  const save = useMutation({
    mutationFn: async () => {
      if (catalog === "products" && product) {
        return updateProduct({
          data: { productCode: product.product_code, name: name.trim(), active },
        });
      }
      if (catalog === "recharges" && recharge) {
        return updateRecharge({
          data: { code: recharge.code, amount: Number(amount), bonusAmount: Number(bonus || 0) },
        });
      }
      if (catalog === "areas" && area) {
        return updateGeoArea({
          data: { areaCode: area.area_code, nameFr: name.trim(), active },
        });
      }
      return undefined;
    },
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });

  const identifier = product?.product_code ?? recharge?.code ?? area?.area_code ?? "";

  return (
    <Modal
      open
      onClose={onClose}
      title="Edit"
      description={identifier}
      className="max-w-[520px]"
      footer={
        <>
          <Button onClick={onClose} disabled={save.isPending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </>
      }
    >
      <div className="space-y-sp-6">
        {catalog !== "recharges" ? (
          <TextField
            label={catalog === "areas" ? "Name (French)" : "Name"}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        ) : (
          <div className="grid gap-sp-5 sm:grid-cols-2">
            <div>
              <label htmlFor="edit-amount" className="t-micro mb-sp-3 block text-ink-5">
                Amount (TND)
              </label>
              <input
                id="edit-amount"
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
            <div>
              <label htmlFor="edit-bonus" className="t-micro mb-sp-3 block text-ink-5">
                Bonus (TND)
              </label>
              <input
                id="edit-bonus"
                type="number"
                min="0"
                step="0.01"
                value={bonus}
                onChange={(event) => setBonus(event.target.value)}
                className={FIELD_CLASS}
              />
            </div>
          </div>
        )}

        {catalog !== "recharges" ? (
          <div className="flex flex-wrap items-center justify-between gap-sp-5 border-t border-stroke-subtle pt-sp-6">
            <div className="min-w-0">
              <p className="t-body-strong text-ink-1">Active</p>
              <p className="t-caption mt-sp-2 max-w-[52ch] text-ink-4">
                {catalog === "products"
                  ? "An inactive plan stays on existing subscriptions but is no longer offered."
                  : "An inactive area is kept for history but stops matching a caller's spoken place."}
              </p>
            </div>
            <SettingToggle name="Active" value={active} onChange={setActive} />
          </div>
        ) : null}

        {save.isError ? <InlineError error={save.error} /> : null}
      </div>
    </Modal>
  );
}

function DeleteDialog({
  catalog,
  identifier,
  onClose,
}: {
  catalog: CatalogKind;
  identifier: string;
  onClose: () => void;
}) {
  const invalidate = useInvalidateCatalog();

  const remove = useMutation({
    mutationFn: async () => {
      if (catalog === "products") return deleteProduct({ data: { productCode: identifier } });
      if (catalog === "recharges") return deleteRecharge({ data: { code: identifier } });
      return deleteGeoArea({ data: { areaCode: identifier } });
    },
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Delete"
      description={identifier}
      footer={
        <>
          <Button onClick={onClose} disabled={remove.isPending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? "Deleting…" : "Delete"}
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-sp-5">
        <AlertTriangle size={16} strokeWidth={1.5} className="mt-sp-2 shrink-0 text-ink-3" />
        <p className="t-ui text-ink-1">
          The agent will stop offering <Token>{identifier}</Token> immediately.
          {catalog === "products"
            ? " If any subscription still points at it, the deletion is refused — deactivate it instead."
            : catalog === "areas"
              ? " If it has child areas or any recorded outage, the deletion is refused — deactivate it instead."
              : ""}
        </p>
      </div>

      {remove.isError ? (
        <div className="mt-sp-6">
          <InlineError error={remove.error} />
        </div>
      ) : null}
    </Modal>
  );
}
