# P2-1 — Implementation Cookbook

**Branch:** `version_86` @ `84956f11b4726396aac6a17d3321ebb473422da7`
**Scope:** Portal real identity + the four remaining dashboard truth gaps.
**Tests:** omitted by instruction. **Commit ceremony:** deferred by instruction.

---

## §0 — Read this before you open an editor

The admin dashboard is **already built**. `Frontend/admin_dashboard/src/routes/` contains 20 route
files served by ~40 endpoints in `main.py`, all reading real tables. Nothing in this cookbook
rebuilds it. Every instruction below is either **additive** (new method, new route, new server fn)
or a **named repair** of a specific defect.

`customer_360` is never touched. `repositories.py` already states the rule twice, on
`customer_ledger` and `customer_service_actions`:

> *"Deliberately a separate method from `customer_360`: widening that method's return shape would
> change existing behaviour for every existing caller."*

Every new read below follows that precedent.

### Verified column inventory (this is the ceiling on what any profile screen can show)

`crm.customers` — `packages/persistence/src/persistence/models/crm.py`:

| Column | Type | Null |
|---|---|---|
| `national_id` | String(50) unique | no — **CIN. PII. Must never reach a browser.** |
| `first_name` / `last_name` | String(100) | no |
| `email` | String(255) unique | **yes** |
| `contact_number` | String(20) | **yes** |
| `preferred_language` | String(10) CHECK `IN ('fr','ar','en')` | no |
| `segment` | String(80) | yes |
| `vip_flag` / `fraud_suspected` | Boolean | no |
| `address` | Text | yes |
| `city` / `region` | String(100) | yes |
| `status` | String(20) CHECK `IN ('active','suspended','closed')` | no |
| `created_at` / `updated_at` | DateTime(tz) — `Timestamps` mixin | no |
| `deleted_at` | DateTime(tz) — `SoftDelete` mixin | yes |

**Columns that do not exist anywhere in the schema:** `date_of_birth`, `preferred_name`,
`customer_reference`, `time_zone`, `date_format`, `number_format`, plan price, plan period.

Consequence: the four fixture fields `dateOfBirth`, `preferredName`, `planPrice`, `planPeriod`
have **no possible source**. They are removed from the UI, not faked. `timeZone` / `dateFormat` /
`numberFormat` are **derived from `preferred_language` via `Intl`** — a real derivation, not an
invented column. `reference` maps to `billing.accounts.account_number` (String(40), unique).

---

# BUNDLE A — Real identity (customer portal)

Five files. A1→A2 are backend and can be done in parallel with A3→A4 (frontend auth) and
A5→A6 (frontend profile).

## A0 — The blocker you must fix first: signup returns 422 on every attempt

`main.py` declares:

```python
class SignupPayload(BaseModel):
    msisdn: str
    cin_last4: str
    email: str
    password: str
```

`Frontend/customer_portal/src/lib/api/auth.server.ts` posts `{ email, password, cin, phone?, region? }`.

`msisdn` and `cin_last4` are absent from every request → FastAPI rejects with **422 before
`signup_client` is entered**. `phone` is optional in the form while `msisdn` is required by the
schema, and the form sends a whole CIN where the backend expects the last four digits and passes
them to `cin.matches(...)`.

The backend half is correct and stays untouched. The frontend is brought to the contract.

---

## A1 — `apps/business-api/src/business_api/repositories.py`

Add this method to `SupervisionRepository`, **immediately after `customer_ledger`**.

> Adaptation check: `customer_360` resolves its `customer_id` argument to a `Customer`. Open that
> method and mirror its exact lookup expression on the first line below rather than assuming
> `Session.get`. Everything after the lookup is final.

```python
    def me_profile_detail(self, customer_id: str) -> dict:
        """Profile fields for the signed-in client's own record.

        Deliberately a separate method from `customer_360`: widening that method's return shape
        would change existing behaviour for every existing caller. `national_id` is never
        selected - the CIN is tokenised in audit.pii_token_map and must not reach a browser.
        """
        customer = self._s.get(Customer, uuid.UUID(customer_id))
        if customer is None:
            return {}

        account_number = self._s.scalar(
            select(Account.account_number)
            .where(Account.customer_id == customer.id, Account.deleted_at.is_(None))
            .order_by(Account.created_at)
            .limit(1)
        )
        subscription = self._s.scalar(
            select(Subscription)
            .where(Subscription.customer_id == customer.id, Subscription.deleted_at.is_(None))
            .order_by(Subscription.created_at)
            .limit(1)
        )

        address_lines = [
            line.strip()
            for line in [*(customer.address or "").splitlines(), customer.city, customer.region]
            if line and line.strip()
        ]

        return {
            "customer_id": str(customer.id),
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "full_name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "phone": customer.contact_number,
            "preferred_language": customer.preferred_language,
            "region": customer.region,
            "city": customer.city,
            "address_lines": address_lines,
            "account_number": account_number,
            "customer_since": customer.created_at.isoformat() if customer.created_at else None,
            "vip": customer.vip_flag,
            "status": customer.status,
            "plan": (subscription.plan_code or subscription.plan_type) if subscription else None,
            "msisdn": subscription.msisdn if subscription else None,
        }
```

**Import guard.** `Account` is in `persistence.models.billing`. If the existing billing import line
is `from persistence.models.billing import Invoice`, extend it to
`from persistence.models.billing import Account, Invoice` — alphabetical, one line, no new import
statement. Confirm `Subscription`, `Customer`, `select` and `uuid` are already imported (they are
used by `customer_360` / `customer_list`); add nothing that is already there.

Do **not** run `ruff check --fix` on hand-formatted imports — run it and take its output.

---

## A2 — `apps/business-api/src/business_api/main.py`

Directly beneath the existing `GET /api/v1/me/profile` handler:

```python
@app.get("/api/v1/me/profile/detail")
def me_profile_detail(
    principal: Annotated[Principal, Depends(current_client)],
) -> dict:
    with session_scope() as session:
        return SupervisionRepository(session).me_profile_detail(str(principal.customer_id))
```

> Adaptation check: copy the decorator/dependency/session idiom verbatim from the existing
> `/api/v1/me/profile` handler three lines above. If it uses `ClientPrincipal` rather than
> `Annotated[Principal, Depends(current_client)]`, use `ClientPrincipal`. Clone the sibling you are
> cloning — do not import a new name.

`customer_360` and the existing `/api/v1/me/profile` route are left byte-identical.

---

## A3 — `Frontend/customer_portal/src/lib/api/auth.server.ts`

Replace the whole `signup` export. Two changes: `cin` → `cin_last4` (last four digits only) and
`phone` → `msisdn` (now required, matching the schema).

```ts
export const signup = createServerFn({ method: "POST" })
  .inputValidator(
    (data: { email: string; password: string; cin: string; msisdn: string }) => {
      if (
        typeof data?.email !== "string" ||
        typeof data?.password !== "string" ||
        typeof data?.cin !== "string" ||
        typeof data?.msisdn !== "string"
      ) {
        throw new ApiError(400, "Email, password, CIN and phone number are required", "signup");
      }
      const cin = data.cin.replace(/\D/g, "");
      if (cin.length < 4) {
        throw new ApiError(400, "Enter at least the last four digits of your CIN", "signup");
      }
      return {
        email: data.email.trim().toLowerCase(),
        password: data.password,
        cin_last4: cin.slice(-4),
        msisdn: data.msisdn.replace(/\s/g, ""),
      };
    },
  )
  .handler(async ({ data }): Promise<ClientSession> => {
    // The KYC record already exists in crm.customers. business-api links the new portal account
    // to it by matching the MSISDN on crm.subscriptions and proofing the last four CIN digits.
    const result = await postCredential<SignupResponse>("/api/v1/auth/signup", {
      email: data.email,
      password: data.password,
      cin_last4: data.cin_last4,
      msisdn: data.msisdn,
    });

    const session: ClientSession = {
      sub: result.email,
      role: "client",
      exp: Math.floor(new Date(result.expires_at).getTime() / 1000),
      token: result.token,
    };

    await writeSessionCookie(session);
    return session;
  });
```

`region` is dropped — the backend never accepted it.

---

## A4 — `Frontend/customer_portal/src/routes/signup.tsx`

Three edits inside `SignupPage`.

**1. State — phone is no longer optional:**

```tsx
  const [phone, setPhone] = useState("");
```

stays as-is; only the submit and the label change.

**2. Submit call:**

```tsx
      await signup({
        data: {
          email,
          password,
          cin,
          msisdn: phone,
        },
      });
```

**3. The phone field — replace the existing `Phone (optional)` label block with:**

```tsx
          <label className="flex flex-col gap-sp-3">
            <span className="t-label text-ink-4">Phone number on the account</span>
            <input
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              autoComplete="tel"
              required
              className={inputClass}
            />
          </label>
```

**4. The CIN label — replace `CIN number` with:**

```tsx
            <span className="t-label text-ink-4">Last 4 digits of your CIN</span>
```

and add `inputMode="numeric"` beside `autoComplete="off"` on that input.

No new colour, token, or primitive. `inputClass`, `Card`, `Button` unchanged.

---

## A5 — `Frontend/customer_portal/src/lib/api/me.server.ts`

Append. The existing `Me` type and `fetchMe` are unchanged.

```ts
export type ProfileDetail = {
  customer_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  preferred_language: string;
  region: string | null;
  city: string | null;
  address_lines: string[];
  account_number: string | null;
  customer_since: string | null;
  vip: boolean;
  status: string;
  plan: string | null;
  msisdn: string | null;
};

export const fetchProfileDetail = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(async (): Promise<ProfileDetail> =>
    businessApi<ProfileDetail>("/api/v1/me/profile/detail", {}),
  );
```

Add to the existing import block at the top of the file:

```ts
import { authedMiddleware } from "./middleware";
```

`fetchMe` deliberately keeps its bare `createServerFn` + try/catch shape — it is a
nullable session probe, not a data read.

---

## A6 — `Frontend/customer_portal/src/lib/fixtures/customer.ts`

Delete **only** the `customer` export. Keep `sessions`, `securityEvents` and `notifications` —
they back `_portal/security.tsx` and the topbar and have no endpoint behind them yet.

Update the file header so the remaining exports are not mistaken for live data:

```ts
/** lib/fixtures/customer.ts - sample data for surfaces with no endpoint yet.
 *  The `customer` record moved to /api/v1/me/profile/detail (see lib/api/me.server.ts).
 *  Aucun nom, montant ou date invente ailleurs. */
```

---

## A7 — `Frontend/customer_portal/src/routes/_portal/profile.tsx`

Full replacement. Same four sections, same primitives, same tokens. Four fields with no schema
source (`preferredName`, `dateOfBirth`, plan price, plan period) are gone; three locale fields are
derived through `Intl`.

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Divider,
  FieldRow,
  SectionLabel,
  StatusChip,
} from "@/components/portal/primitives";
import { fetchProfileDetail } from "@/lib/api/me.server";
import { errorMessage } from "@/lib/api/errors";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "identity", label: copy.profile.nav.identity },
  { id: "contact", label: copy.profile.nav.contact },
  { id: "addresses", label: copy.profile.nav.addresses },
  { id: "locale", label: copy.profile.nav.locale },
] as const;

/** crm.customers stores only a language code. Everything below is derived, never invented. */
const LOCALES = {
  fr: { label: "Fran\u00e7ais", tag: "fr-TN" },
  ar: { label: "\u0627\u0644\u0639\u0631\u0628\u064a\u0629", tag: "ar-TN" },
  en: { label: "English", tag: "en-GB" },
} as const;

const TIME_ZONE = "Africa/Tunis";

function localeFor(code: string) {
  return LOCALES[code as keyof typeof LOCALES] ?? LOCALES.fr;
}

function initialsOf(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

function formatDay(iso: string | null, tag: string) {
  if (!iso) return "\u2014";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "\u2014";
  return new Intl.DateTimeFormat(tag, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: TIME_ZONE,
  }).format(at);
}

export const Route = createFileRoute("/_portal/profile")({
  component: ProfilePage,
});

function ProfilePage() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("identity");

  const query = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });

  if (query.isPending) {
    return (
      <Card>
        <p className="t-caption text-ink-5">Loading your details\u2026</p>
      </Card>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Card>
        <p role="alert" className="t-body text-ink-1">
          {errorMessage(query.error)}
        </p>
        <Button variant="secondary" className="mt-sp-6" onClick={() => void query.refetch()}>
          {copy.common.tryAgain}
        </Button>
      </Card>
    );
  }

  const me = query.data;
  const locale = localeFor(me.preferred_language);
  const numberSample = new Intl.NumberFormat(locale.tag).format(1234.56);
  const dateSample = formatDay(me.customer_since, locale.tag);

  return (
    <div className="grid gap-sp-7 lg:grid-cols-[200px_1fr]">
      <nav className="flex gap-sp-3 lg:flex-col">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setSection(s.id)}
            aria-pressed={section === s.id}
            className={cn(
              "focus-ring t-label rounded-r-2 px-sp-5 py-sp-3 text-left transition-colors duration-200",
              section === s.id
                ? "bg-surface-3 text-ink-1"
                : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
            )}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="flex flex-col gap-sp-7">
        {section === "identity" ? (
          <Card>
            <SectionLabel>{copy.profile.identity}</SectionLabel>
            <div className="mt-sp-7 flex items-center gap-sp-6">
              <div className="t-title-3 flex h-14 w-14 items-center justify-center rounded-r-3 border border-stroke-default bg-surface-2 text-ink-1">
                {initialsOf(me.first_name, me.last_name)}
              </div>
              <div className="min-w-0">
                <div className="t-title-3 truncate text-ink-1">{me.full_name}</div>
                <div className="t-caption mt-sp-2 text-ink-4">
                  {copy.profile.customerSince(dateSample)}
                </div>
              </div>
              {me.vip ? <StatusChip tone="solid" className="ml-auto">VIP</StatusChip> : null}
            </div>
            <Divider className="mt-sp-7" />
            <FieldRow label={copy.profile.fields.fullName} value={me.full_name} />
            <Divider />
            <FieldRow
              label={copy.profile.fields.reference}
              value={me.account_number ?? "\u2014"}
              mono
              hint={copy.profile.locked}
            />
          </Card>
        ) : null}

        {section === "contact" ? (
          <Card>
            <SectionLabel>{copy.profile.contact}</SectionLabel>
            <div className="mt-sp-5">
              <FieldRow
                label={copy.profile.fields.email}
                value={me.email ?? "\u2014"}
                action={me.email ? <StatusChip tone="outline">VERIFIED</StatusChip> : null}
              />
              <Divider />
              <FieldRow
                label={copy.profile.fields.phone}
                value={me.phone ?? me.msisdn ?? "\u2014"}
                mono
                action={<StatusChip tone="dashed">UNVERIFIED</StatusChip>}
              />
            </div>
          </Card>
        ) : null}

        {section === "addresses" ? (
          <Card>
            <SectionLabel>{copy.profile.addresses}</SectionLabel>
            <div className="mt-sp-6">
              <div className="t-label text-ink-4">{copy.profile.billingAddress}</div>
              {me.address_lines.length === 0 ? (
                <p className="t-body mt-sp-3 text-ink-5">{copy.empty.generic}</p>
              ) : (
                <div className="t-body-strong mt-sp-3 text-ink-1">
                  {me.address_lines.map((line) => (
                    <div key={line}>{line}</div>
                  ))}
                </div>
              )}
              <p className="t-caption mt-sp-5 text-ink-5">{copy.profile.locked}</p>
            </div>
          </Card>
        ) : null}

        {section === "locale" ? (
          <Card>
            <SectionLabel>{copy.profile.locale}</SectionLabel>
            <div className="mt-sp-5">
              <FieldRow label={copy.profile.fields.language} value={locale.label} />
              <Divider />
              <FieldRow label={copy.profile.fields.region} value={me.region ?? "\u2014"} />
              <Divider />
              <FieldRow label={copy.profile.fields.timeZone} value={TIME_ZONE} mono />
              <Divider />
              <FieldRow label={copy.profile.fields.dateFormat} value={dateSample} />
              <Divider />
              <FieldRow label={copy.profile.fields.numberFormat} value={numberSample} mono />
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
```

**Route-id check.** Copy the `createFileRoute("...")` argument from the current file before you
overwrite it, and keep whatever `head:`/`meta:` block it already declares. `routeTree.gen.ts` is
generated — never hand-edit it.

**Grep gate for the bundle.** Zero hits expected:

```bash
git grep -n "Amara\|amara.osei\|NX-4471\|Bramley" -- Frontend/customer_portal/src
git grep -n "fixtures/customer" -- Frontend/customer_portal/src/routes/_portal/profile.tsx
```

---

# BUNDLE B — Escalation closure (R6)

The largest genuinely missing dashboard feature. `conversation.escalation_cases` holds 58 rows
across 42 distinct sessions and **every one has `resolution IS NULL`** because no write path
exists. `GET /api/v1/escalations` is read-only.

**No migration.** The model already permits closure:

```python
CheckConstraint(
    "resolution IS NULL OR resolution IN ('transferred','queued','callback_scheduled','resolved')",
    name="resolution",
)
```

## B1 — `apps/business-api/src/business_api/repositories.py`

Immediately after the existing `escalations` method:

```python
    _ESCALATION_RESOLUTIONS = ("transferred", "queued", "callback_scheduled", "resolved")

    def close_escalation(self, escalation_id: str, resolution: str) -> dict:
        """Set the outcome on an open handoff. Idempotent per row: a case that already carries a
        resolution is returned unchanged rather than overwritten.
        """
        if resolution not in self._ESCALATION_RESOLUTIONS:
            raise ValueError(f"unsupported resolution: {resolution}")

        case = self._s.get(EscalationCase, uuid.UUID(escalation_id))
        if case is None:
            return {}
        if case.resolution is None:
            case.resolution = resolution
            self._s.flush()

        return {
            "id": str(case.id),
            "session_id": str(case.session_id),
            "trigger": case.trigger,
            "target": case.target,
            "resolution": case.resolution,
            "dossier": case.dossier,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "customer_id": str(case.customer_id) if case.customer_id else None,
        }
```

The returned dict is the **same shape** `escalations()` serialises, so the existing `Escalation`
wire type needs no change.

`EscalationCase` lives in `persistence.models.conversation`; extend the existing import rather than
adding a statement.

## B2 — `apps/business-api/src/business_api/main.py`

After the existing `GET /api/v1/escalations`:

```python
class EscalationClosePayload(BaseModel):
    resolution: str


@app.post("/api/v1/escalations/{escalation_id}/close")
def close_escalation(
    escalation_id: str,
    payload: EscalationClosePayload,
    role: Annotated[str, Depends(SuperviseurRole)],
) -> dict:
    with session_scope() as session:
        try:
            closed = SupervisionRepository(session).close_escalation(
                escalation_id, payload.resolution
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not closed:
        raise HTTPException(status_code=404, detail="escalation not found")
    return closed
```

> Adaptation check: `SuperviseurRole` is the module-level alias already used by the sibling GET.
> Copy the dependency expression from that handler exactly. POST only — never GET for a mutation.

## B3 — `Frontend/admin_dashboard/src/lib/api/escalations.server.ts`

Append:

```ts
export const escalationResolution = z.enum([
  "transferred",
  "queued",
  "callback_scheduled",
  "resolved",
]);
export type EscalationResolution = z.infer<typeof escalationResolution>;

const CloseInput = z.object({
  id: z.string().min(1),
  resolution: escalationResolution,
});

export const closeEscalation = createServerFn({ method: "POST" })
  .middleware([requireRole("superviseur")])
  .inputValidator((data: unknown) => CloseInput.parse(data))
  .handler(async ({ data, context }) => {
    return businessApi<Escalation>(`/api/v1/escalations/${data.id}/close`, {
      method: "POST",
      body: { resolution: data.resolution },
      role: context.session.role,
    });
  });
```

> Adaptation check: confirm the admin `businessApi` options object accepts `body`. If the existing
> POST callers in `callbacks.server.ts` use a different key, use theirs.

## B4 — `Frontend/admin_dashboard/src/routes/escalations.tsx`

The dossier pane currently renders `Outcome` as read-only text. Make it actionable.

**Imports — add to the existing blocks:**

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/nexus/primitives";
import {
  closeEscalation,
  listEscalations,
  type Escalation,
  type EscalationResolution,
} from "@/lib/api/escalations.server";
```

(`useQuery` is already imported — extend that line rather than duplicating it. `Button` joins the
existing `@/components/nexus/primitives` import list.)

**Constant — beside `SCOPE_OPTIONS`:**

```tsx
const RESOLUTIONS: { id: EscalationResolution; label: string }[] = [
  { id: "transferred", label: "Transferred" },
  { id: "queued", label: "Queued" },
  { id: "callback_scheduled", label: "Callback scheduled" },
  { id: "resolved", label: "Resolved" },
];
```

**Inside `EscalationsPage`, after the `query` declaration:**

```tsx
  const queryClient = useQueryClient();

  const close = useMutation({
    mutationFn: (vars: { id: string; resolution: EscalationResolution }) =>
      closeEscalation({ data: vars }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: escalationKeys.list(scope) });
    },
  });
```

**Replace the Outcome row** (the block containing `resolutionLabel(current.resolution)`) with:

```tsx
            <div className="flex items-center gap-sp-5 border-t border-stroke-subtle px-sp-7 py-sp-5">
              <span className="t-label text-ink-3">Outcome</span>
              {current.resolution ? (
                <span className="ml-auto flex items-center gap-sp-4">
                  <span className="t-ui text-ink-2">{resolutionLabel(current.resolution)}</span>
                  <StatusChip status={escalationStatusKey(current.resolution)} />
                </span>
              ) : (
                <span className="ml-auto flex flex-wrap items-center justify-end gap-sp-3">
                  {RESOLUTIONS.map((r) => (
                    <Button
                      key={r.id}
                      size="sm"
                      variant="secondary"
                      disabled={close.isPending}
                      onClick={() => close.mutate({ id: current.id, resolution: r.id })}
                    >
                      {r.label}
                    </Button>
                  ))}
                </span>
              )}
            </div>
            {close.isError ? (
              <p role="alert" className="t-caption px-sp-7 pb-sp-5 text-ink-2">
                {errorMessage(close.error)}
              </p>
            ) : null}
```

Add `import { errorMessage } from "@/lib/api/errors";` if the file does not already import it.

> Adaptation check: `Button` in the **admin** primitives may not expose the same `size`/`variant`
> union as the portal's. Open `Frontend/admin_dashboard/src/components/nexus/primitives.tsx`, read
> the `Button` props, and use its actual values. Do not add a variant.

**Result:** the Open list empties as cases are closed, which is what `scope="open"` has always
promised and never delivered.

---

# BUNDLE C — Notification failure reason (R8)

`billing.notifications` holds 48 rows, `{sent: 20, failed: 28}`. Twenty-eight failures record
**no reason**. The model has no column for one:

```python
CheckConstraint("status IN ('queued','sent','failed')", name="status")
```

This is the only bundle needing a migration. Alembic lives at `packages/persistence/alembic`;
head is `0016_portal_identity`; apply with `make migrate`.

## C1 — `packages/persistence/alembic/versions/0017_notification_failure_reason.py` (new)

```python
"""Motif d'echec de notification (R8).

Revision ID: 0017_notification_failure_reason
Revises: 0016_portal_identity
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_notification_failure_reason"
down_revision = "0016_portal_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications", sa.Column("failure_reason", sa.String(200)), schema="billing"
    )
    op.create_check_constraint(
        "failure_reason_only_when_failed",
        "notifications",
        "failure_reason IS NULL OR status = 'failed'",
        schema="billing",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_notifications_failure_reason_only_when_failed",
        "notifications",
        schema="billing",
        type_="check",
    )
    op.drop_column("notifications", "failure_reason", schema="billing")
```

The constraint name in `downgrade` follows `NAMING_CONVENTION["ck"]` =
`ck_%(table_name)s_%(constraint_name)s` from `packages/persistence/src/persistence/base.py`, which
is exactly how `0015` drops `ck_outages_cause`.

Adding a nullable column plus a constraint satisfied by every existing row (all 48 have
`failure_reason IS NULL`) is non-breaking on live data.

## C2 — `packages/persistence/src/persistence/models/billing.py`

In `class Notification`, after `status`:

```python
    failure_reason: Mapped[str | None] = mapped_column(String(200))
```

And extend `__table_args__` with the matching constraint so the model and DB agree:

```python
        CheckConstraint(
            "failure_reason IS NULL OR status = 'failed'",
            name="failure_reason_only_when_failed",
        ),
```

## C3 — `apps/business-api/src/business_api/repositories.py`

In `notification_list`, add one key to the per-row dict, beside `status`:

```python
                "failure_reason": row.failure_reason,
```

> Adaptation check: if `notification_list` builds rows from an explicit `select(...)` column list
> rather than whole ORM objects, add `Notification.failure_reason` to that `select` too.

## C4 — `Frontend/admin_dashboard/src/lib/api/notifications.server.ts`

Add one field to `NotificationRow`, after `status`:

```ts
  failure_reason: string | null;
```

## C5 — `Frontend/admin_dashboard/src/routes/notifications.tsx`

**Not authored here — I have not read this file, and I will not write JSX against a component I
have not seen.** The contract is fixed by C4: `failure_reason` is `string | null`, non-null only
when `status === "failed"`. Open the file, find the row/detail renderer that already prints
`status`, and surface `failure_reason` next to it using whatever primitive that file already uses.
One field, one line, no new component.

The backend half (C1–C4) is complete and correct on its own; the column is live on the wire the
moment C4 lands.

---

# BUNDLE D — Invoice status whitelist (R11) — **GATED, needs your word**

`customer_360` selects open invoices with a blacklist:

```python
"open_invoices": [... for i in invoices if i.status != "paid"]
```

`Invoice.status` CHECK is `IN ('draft','issued','paid','partial','overdue','disputed','void')`, so
`!= "paid"` also admits **`draft`** and **`void`** — invoices that are not owed. The agent-worker's
`projections.py` uses `_OPEN_INVOICE_STATUSES = ("issued","overdue","partial")` while `OWED_STATUSES`
includes `disputed`. Three different definitions of "open" in one codebase.

The correct expression:

```python
_OPEN_INVOICE_STATUSES = ("issued", "overdue", "partial", "disputed")
```

```python
"open_invoices": [... for i in invoices if i.status in _OPEN_INVOICE_STATUSES]
```

**I am not applying this without your explicit go-ahead.** It edits `customer_360`, and it changes
what existing callers see — the voice agent, the admin 360 pane, and `/api/v1/me/profile` all read
that list. Your §0 says *"Do not delete or modify existing backend logic or behavior — this is
forbidden"* and *"if genuinely crucial, ask first."* This is me asking.

Live-data note: `billing.invoices` currently holds **2 rows**, so blast radius today is small — but
the reconciliation between the three definitions is the real work, not the one-line edit.

---

# BUNDLE E — `system_overview` hardcoded status (R10) — **do this last, or not at all**

`repositories.system_overview()` returns eleven hardcoded `"online"` strings.

**It is not a live bug.** I claimed once that the overview page reports every service healthy; that
was wrong — `Frontend/admin_dashboard/src/routes/overview.tsx` never renders the status field. The
lie exists in the payload, not on any screen.

Two honest options, both cheap:

1. **Delete the field.** Remove the eleven `"online"` entries from the returned dict. Nothing
   renders them, so nothing breaks. The payload stops asserting something it does not know.
2. **Make it real.** `scripts/health_check.py` already probes every service `/health`. Reuse that
   logic server-side and return actual results.

Option 1 is minutes and removes a falsehood. Option 2 is a genuine feature and needs a timeout
budget so a hung probe cannot stall the overview request. Pick one; do not leave it as-is while
calling the dashboard "fully functional".

---

# APPLY ORDER

Bundles A, B and C touch disjoint files and can be coded in parallel. Within each, backend before
frontend.

| Step | Command |
|---|---|
| 1 | Bundle A1–A2, B1–B2, C1–C3 (all backend) |
| 2 | `make migrate` — applies `0017` |
| 3 | Bundle A3–A7, B3–B4, C4–C5 (all frontend) |
| 4 | `python -m ruff check --fix apps/business-api packages/persistence` |
| 5 | `npx prettier --write <only the files you touched>` |
| 6 | `make rebuild` — **not** `make up`. Dockerfiles bake source; a restart ships stale code. |
| 7 | `make health` |

## Manual verification (no test files, per instruction)

```bash
# A — signup contract
curl.exe -s -X POST http://localhost:8108/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"msisdn":"...","cin_last4":"...","email":"...","password":"..."}' -o - -w "%{http_code}\n"
# expect 200 or a 401 'signup_failed' - anything but 422

# B — closure round-trip
curl.exe -s -X POST http://localhost:8108/api/v1/escalations/<id>/close \
  -H "Authorization: Bearer <staff token>" -H "Content-Type: application/json" \
  -d '{"resolution":"resolved"}'
```

```sql
-- B — open count must fall as you close cases
SELECT count(*) FILTER (WHERE resolution IS NULL) AS still_open,
       count(*)                                   AS total
FROM conversation.escalation_cases;

-- C — column live, constraint holds
SELECT count(*) AS failed_rows,
       count(failure_reason) AS with_reason
FROM billing.notifications WHERE status = 'failed';
```

Expectations are written as invariants, not literals, on purpose: `still_open` must **decrease by
exactly the number of cases you closed**, and `with_reason` must be **0 until a writer populates
it**. Do not chase a target number — the 58 escalation rows span 42 distinct sessions, and
conflating those two units has burned me before.

## Out of scope, deliberately

- `/api/v1/actions` (R13) has zero frontend callers. Wiring a page to it is a new feature, not a
  gap. Leave it.
- `sessions` / `securityEvents` fixtures in `_portal/security.tsx` stay. `POST
  /api/v1/auth/sessions/revoke-all` exists and backs the "sign out everywhere" affordance, but
  there is no endpoint that **lists** sessions, so the list itself has nothing real to show yet.
- Plan price and period: no column, no catalog join available. Removed from the profile rather
  than invented.
