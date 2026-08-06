# FEATURE_18 — Notification send log (sms / whatsapp / email)

> Branch of truth: `version_81` @ `2f10a07`. Operator's local HEAD: `f584eef` (FEATURE_15 + 16 + 17 applied, uncommitted).
> Scope: one additive GET route + one repository method (backend), one new admin page + nav destination (frontend).
> Baseline moves **26 -> 28 passed** (two deterministic contract tests, neither inserts a row).

---

## 1. Feature name & scope

**Notification send log** — a read-only supervision page over `billing.notifications`, the durable
record the notification-service writes after **every** outbound send attempt.

This is the last projection-adjacent table with a real writer that no admin screen can read.
FEATURE_16 exposed money (payments / plans / consent), FEATURE_17 exposed effects (balances /
plan history / service actions). This exposes **communication**: what the platform actually told
the customer, on which channel, and whether it went out.

### 1.1 Why this is not a duplicate of anything already shipped

| Existing surface | What it shows | What it cannot show |
| --- | --- | --- |
| `/tickets` | GLPI ticket rows, `last_synced_at` | whether the caller was ever *told* their ticket was opened |
| `/callbacks` | the booked slot + outcome | whether the confirmation message reached them |
| `/decisions` | verdicts + `execution.action_ledger` attempts | nothing — notifications are not actions and carry no `policy_verdict_id` |
| `/escalations` | the handoff case | whether the advisor was actually paged |

`billing.notifications` is written on a **completely separate path** from `execution.action_ledger`.
It is not a projection of an authorised action; it is written directly by
`NotificationService._record` on every call to `/notify`. That matters for a practical reason:
`action_ledger` is empty-ish in the dev DB, but notifications are written by the ticketing MCP
server on **every ticket the agent opens**, so this page has an independent chance of holding data.

### 1.2 Writer verification (the `CustomerInteraction` test)

FEATURE_16 rejected `crm.CustomerInteraction` because it has **zero writers**. Same check, run first,
for `billing.Notification`:

```
git grep -n "Notification(" -- services/ apps/ mcp-servers/ packages/
```

**Writer found — `services/notification-service/src/notification_service/service.py`:**

```python
    @staticmethod
    def _persist(req: NotifyRequest, status: str) -> None:
        from persistence.engine import session_scope
        from persistence.models.billing import Notification
        from persistence.util import to_uuid

        with session_scope() as session:
            session.add(Notification(
                customer_id=to_uuid(req.customer_id),
                channel=req.channel,
                template_code=req.template,
                status=status,
            ))
```

There is also a dedicated migration, `packages/persistence/alembic/versions/0005_ticketing_notifications.py`,
which imports `Notification` and `Ticket` together. The table is real, migrated, and written.
**Constraint 3 is satisfied: this exposes existing data, it does not create business logic.**

---

## 2. Backend reference (exact names / paths, all verified at `2f10a07`)

### 2.1 The model — `packages/persistence/src/persistence/models/billing.py`

```python
class Notification(UUIDPrimaryKey, Base):
    """Outbound customer notification log (spec section 5.2): reminder/alert/confirmation dispatch."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('sms','whatsapp','email')", name="channel"),
        CheckConstraint("status IN ('queued','sent','failed')", name="status"),
        {"schema": "billing"},
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm.customers.id"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'sent'"))
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
```

Four things about this model drive every decision below:

1. **It does not use the `Timestamps` mixin.** There is no `updated_at`. A notification is an
   append-only event, never revised.
2. **`customer_id` is nullable** and there are two live paths that write NULL (see §2.3).
3. **There is no `reason` / `error` column**, even though the service computes one (see §2.4).
4. **There is no `session_id`**, so a notification cannot be linked back to the call that caused it.

### 2.2 The write path — `services/notification-service/src/notification_service/`

| File | Role |
| --- | --- |
| `main.py` | `POST /notify` -> `NotificationService.notify` |
| `service.py` | render -> send -> `_record` -> `_persist` |
| `contacts.py` | `resolve_recipient(customer_id, channel)` from `crm.customers`; raises `ContactUnavailable` |
| `templates.py` | `TEMPLATES` — the five template codes |
| `channels.py` | provider adapters; raises `ChannelUnavailable` |

The module docstring states the contract this page is built on:

> *"Live-only, no mock fallback. If a channel is unconfigured or the provider rejects the message,
> sent=False is returned with the actual reason. The DB record is written with status='failed'."*

So a `failed` row is **a real refusal**, not a gap. Three distinct failure modes all land as `failed`:

| Failure | Raised by | Recorded |
| --- | --- | --- |
| customer has no handle for that channel | `ContactUnavailable` (`contacts.py`) | `status="failed"` |
| channel not configured | `ChannelUnavailable` (`channels.py`) | `status="failed"` |
| provider rejected the message | bare `except Exception` | `status="failed"` |

### 2.3 Why `customer_id` is NULL for a whole class of rows (drives D18.1)

`_persist` calls `to_uuid(req.customer_id)`. From `packages/persistence/src/persistence/util.py`:

```python
def to_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Parse ``value`` as a UUID, or None for empty input."""
    if not value:
        return None
    ...
    except (ValueError, AttributeError):
        return None
```

It returns `None` — never raises — for both empty and non-UUID input. Two live callers hit that:

**(a) Advisor notifications.** `apps/agent-worker/src/clients/notification_client.py`:

```python
    async def notify_advisor(
        self, channel: str, to: str, template: str, language: str, params: dict
    ) -> bool:
        """Send a message to an ADVISOR (not a customer), addressed explicitly.
        ..."""
        resp = await self._client.post(
            "/notify",
            json={
                "customer_id": "", "to": to, "channel": channel,
                ...
```

`customer_id: ""` -> `to_uuid("")` -> `None`. **Every advisor page is stored unattributed.**
The `advisor_callback` template in `templates.py` exists precisely for these.

**(b) Non-UUID caller ids.** `services/notification-service/tests/test_notification.py` calls
`NotifyRequest(customer_id="TT-100021", ...)` — an external customer code. `to_uuid` returns `None`
for that too, so the row is written with a NULL customer.

> **This is the single fact that decides the shape of the feature.** A per-customer section inside
> the 360 modal would render the entire advisor-notification channel invisible, because those rows
> have no customer to hang off. A cross-entity list page is the only honest container. See D18.1.

**Open verification item for the operator:** `search_code` for `notify_advisor` returned **0 hits**
across the repo — but the method definition is plainly in `notification_client.py`, which I read
directly. GitHub's code-search index is therefore not reliable for this token, and I will not claim
from it either that the method has callers or that it has none. Please run locally:

```
git grep -n "notify_advisor\|advisor_callback" -- apps/ services/ mcp-servers/
```

The feature is correct either way — NULL rows also arise from path (b) — but the caption wording in
§4.6 is worth tuning to the answer.

### 2.4 The failure reason is computed and then discarded (constraint-3 flag, do not build)

`NotifyResponse` carries `reason`, and `service.py` fills it accurately:

```python
        except ChannelUnavailable as exc:
            reference = ""
            sent = False
            reason = str(exc)
            status = "failed"
```

But `_persist` writes only `customer_id`, `channel`, `template_code`, `status`. **The reason never
reaches the database.** So this page can say *that* a send failed but not *why*.

Storing it would require a new column -> a model change in `packages/persistence` -> a new Alembic
migration. That is new business logic and a locked directory. **Flagged, not built** — same disposition
as FEATURE_17's SIM-order dead end (operator decision §6.B). Recorded in §6-D as a candidate cookbook.

### 2.5 Two more honesty facts about the write path

```python
    def _record(self, req: NotifyRequest, status: str, reference: str) -> None:
        self._sent.append({...})
        if os.getenv("DATABASE_URL"):
            try:
                self._persist(req, status)
            except Exception as exc:
                logger.warning("notification log write skipped: %s", exc)
```

1. **Persistence is conditional** on `DATABASE_URL` being set in the notification-service process.
2. **A failed insert is swallowed** with a `logger.warning`. The log can under-report; it can never
   over-report. The page caption says so rather than implying completeness.

### 2.6 `sent_at` is not a delivery timestamp (drives D18.5)

`_persist` never sets `sent_at`. The column's `server_default=text("now()")` fills it at INSERT —
including for `status="failed"` rows. So `sent_at == created_at` for every row the current writer
produces, and a `failed` row still carries a `sent_at`.

Rendering a column called "Sent" from that value would assert a delivery that did not happen. The
column is labelled **"Logged"** and sourced from `created_at`. This is exactly the precedent
`/tickets` already set — `routes/tickets.tsx` heads its time column `Synced`, not `Updated`, with the
comment *"F8 — "Synced", not "Updated": last_synced_at is when we last agreed with GLPI."*

### 2.7 The five template codes — `templates.py`

`TEMPLATES` keys, verbatim: `advisor_callback`, `ticket_created`, `callback_scheduled`,
`ticket_resolved`, `ticket_updated`.

`template_code` is a nullable `String(80)`, **not** an enum and **not** CHECK-constrained, so the label
map must fall through to the raw string rather than hide an unmapped code.

### 2.8 Existing endpoints — none

```
git grep -n "notifications" -- apps/business-api/
```

No route, no repository method. `SupervisionRepository` does not import `Notification`. There is
nothing to reuse and nothing to duplicate.

---

## 3. Endpoints

### 3.1 Existing to reuse

`GET /api/v1/advisors/coverage` (`superviseur`) — already called by `/tickets`, `/callbacks`,
`/calls` and `/availability` purely to obtain `timezone`. The new page joins that shared cache; it
adds no request.

### 3.2 New endpoint

```
GET /api/v1/notifications?limit=&offset=&channel=&status=
```

| Item | Value |
| --- | --- |
| Role | **`superviseur`** |
| File | `apps/business-api/src/business_api/main.py` |
| Position | immediately after the `ticket_index` handler, before `session_index` |
| CORS / middleware | **none** — `require_role` factory and the existing `CORSMiddleware` block are reused verbatim |

**Role justification.** `BATCH_1_APPLY` §1 invariant: *aggregate / cross-entity lists -> `superviseur`;
single-entity reads reached from an entity you already hold -> `conseiller`.* This is a cross-entity
list, so `superviseur` — matching `/api/v1/tickets`, `/api/v1/sessions`, `/api/v1/decisions`. It is
deliberately **not** `conseiller` like FEATURE_16/17's per-customer routes, because this one is not
reached from a customer you already hold.

**Response shape** (identical key layout to `/api/v1/tickets`, so the frontend list pattern ports 1:1):

```json
{
  "notifications": [
    {
      "id": "0e1c…",
      "customer_id": "2187de39-3a84-4c1c-872f-b6711dc9f7a1",
      "customer_name": "Sami Ben Salah",
      "customer_vip": false,
      "channel": "whatsapp",
      "template_code": "ticket_created",
      "status": "sent",
      "sent_at": "2026-08-05T22:30:33+00:00",
      "created_at": "2026-08-05T22:30:33+00:00"
    }
  ],
  "total": 128,
  "counts": { "sent": 120, "failed": 8 },
  "limit": 50,
  "offset": 0
}
```

### 3.3 Deliberately **not** in the query surface

| Omitted | Why |
| --- | --- |
| `template` filter | no UI control consumes it in this cookbook; adding an unwired parameter is dead surface. Three lines to add later — raised as §6-C. |
| `customer_id` filter | same. It only becomes useful if the 360 modal ever links here, which is not in scope. |
| `search` | `/tickets` searches `subject`/`glpi_ticket_id`. `notifications` has no free-text column at all — `template_code` is a closed vocabulary better served by a filter than a text box. |

---

## 4. Implementation plan

### 4.1 `apps/business-api/src/business_api/repositories.py`

**Import change — modify the existing line, do not add a new one.**

The file currently reads (after FEATURE_16 added `Payment, PaymentPlan`):

```python
from persistence.models.billing import Invoice, Payment, PaymentPlan
```

Becomes:

```python
from persistence.models.billing import Invoice, Notification, Payment, PaymentPlan
```

`Notification` sorts between `Invoice` and `Payment`, so ruff `I001` stays clean.

> **No sqlalchemy import change.** Line 6 already reads `from sqlalchemy import func, or_, select` —
> all three symbols this method needs are present. Do **not** add a second sqlalchemy import line.

**New module constant** — place beside the existing `_LEDGER_LIMIT` / `_SERVICE_LIMIT` constants:

```python
_NOTIFICATION_LIMIT_MAX = 200
```

**New method** — append immediately after `customer_service_actions()` (FEATURE_17's method), keeping
the file's "newest read last" ordering.

```python
    def notification_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        channel: str | None = None,
        status: str | None = None,
    ) -> dict:
        """Outbound notification sends (billing.notifications), newest first.

        Read-only. The notification-service owns the write path and records every attempt,
        successful or not, so a ``failed`` row is a real refusal rather than a gap.

        ``customer_id`` is nullable by design: notify_advisor() posts an empty customer_id and
        to_uuid() turns that into NULL, so advisor pages are unattributed rather than missing.
        The list is therefore never scoped to a customer - doing so would hide them.
        """
        stmt = select(Notification)
        count_stmt = select(func.count()).select_from(Notification)

        def _both(clause):
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if channel:
            _both(Notification.channel == channel)
        if status:
            _both(Notification.status == status)

        total = self._s.scalar(count_stmt) or 0
        limit = max(1, min(limit, _NOTIFICATION_LIMIT_MAX))
        offset = max(0, offset)

        rows = self._s.scalars(
            stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        ).all()

        customer_ids = {r.customer_id for r in rows if r.customer_id}
        customers = {}
        if customer_ids:
            customers = {
                c.id: c
                for c in self._s.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
            }

        counts = {
            row[0]: row[1]
            for row in self._s.execute(
                select(Notification.status, func.count()).group_by(Notification.status)
            ).all()
        }

        items = []
        for r in rows:
            customer = customers.get(r.customer_id)
            items.append({
                "id": str(r.id),
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "customer_name": f"{customer.first_name} {customer.last_name}".strip() if customer else None,
                "customer_vip": bool(customer.vip_flag) if customer else False,
                "channel": r.channel,
                "template_code": r.template_code,
                "status": r.status,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return {
            "notifications": items, "total": total, "counts": counts,
            "limit": limit, "offset": offset,
        }
```

**Provenance — every construct here is copied from `ticket_list` in the same file:**

| Construct | Copied from |
| --- | --- |
| `self._s` | every method in the class (the FEATURE_17 correction) |
| the `_both(clause)` nonlocal closure | `ticket_list`, lines beginning `def _both(clause):` |
| `total` before the clamp, then `max(1, min(limit, 200))` / `max(0, offset)` | `ticket_list`, verbatim ordering |
| batched `customers` dict via `Customer.id.in_(customer_ids)` | `ticket_list` and `session_list` |
| `f"{customer.first_name} {customer.last_name}".strip() if customer else None` | `ticket_list`, character-for-character |
| `bool(customer.vip_flag) if customer else False` | `ticket_list` |
| `counts` via `select(Model.status, func.count()).group_by(...)` | `ticket_list` |
| `{"…": items, "total": …, "counts": …, "limit": …, "offset": …}` | `ticket_list` return line |

> **Counts are global, not filtered — and that is deliberate.** `ticket_list` builds its `counts`
> from an unfiltered `group_by`, so the status tiles keep showing the full breakdown while a filter
> is active (which is what makes them usable as toggles). I am matching that behaviour exactly
> rather than "fixing" it, because the UI in §4.5 uses the tiles as filter buttons in the same way
> `/tickets` does. Diverging here would make the two pages behave differently for no stated reason.

`national_id` is never referenced. Only `first_name`, `last_name`, `vip_flag` are read off `Customer`.

### 4.2 `apps/business-api/src/business_api/main.py`

Insert after `ticket_index`, before `session_index`:

```python
@app.get("/api/v1/notifications")
def notification_index(session: DbSession, role: SuperviseurRole, limit: int = 50,
                       offset: int = 0, channel: str | None = None,
                       status: str | None = None) -> dict:
    """Outbound notification sends (billing.notifications), newest first.

    Read-only. The notification-service owns the write path; this endpoint never sends anything
    and never retries a failed send.
    """
    return SupervisionRepository(session).notification_list(
        limit=limit, offset=offset, channel=channel, status=status,
    )
```

This reproduces `ticket_index`'s exact conventions, including the three FEATURE_17 corrections:
`role: SuperviseurRole` is **named** (not `_:`), the return annotation is bare **`-> dict`** (`main.py`
imports no `Any`), and the continuation lines align under the opening paren.

No `HTTPException`: a list with no matches is an empty list, not a 404. Same as `ticket_index`.
**No CORS hunk. No middleware hunk.**

### 4.3 `apps/business-api/tests/test_notification_list.py` — new

```python
"""Contract tests for the notification send log (FEATURE_18).

Neither test inserts a row. billing.notifications has no NOT NULL column the tests could
violate, but crm.customers.national_id is nullable=False and cookbooks forbid setting it, so
the FEATURE_16 lesson stands: assert on shape and clamping, never on seeded content.
"""
from business_api.repositories import SupervisionRepository


def test_notification_list_shape_and_clamps(db_session):
    """The five documented keys are always present, and limit/offset are clamped, not trusted."""
    result = SupervisionRepository(db_session).notification_list(limit=0, offset=-5)

    assert set(result) == {"notifications", "total", "counts", "limit", "offset"}
    assert result["limit"] == 1
    assert result["offset"] == 0
    assert isinstance(result["notifications"], list)
    assert isinstance(result["counts"], dict)
    assert isinstance(result["total"], int)


def test_notification_list_unknown_channel_returns_nothing(db_session):
    """An out-of-enum channel filters everything out rather than being ignored."""
    result = SupervisionRepository(db_session).notification_list(channel="carrier-pigeon")

    assert result["notifications"] == []
    assert result["total"] == 0
```

The second test is the one that would silently pass if `_both` were wired to only one of the two
statements — it asserts the filter reaches the **count** query, not just the row query.

`db_session` is the existing fixture in `apps/business-api/tests/conftest.py` (live docker-postgres
engine inside a rolled-back transaction). Baseline **26 -> 28 passed**.

### 4.4 `Frontend/admin_dashboard/src/lib/api/notifications.server.ts` — new

A structural clone of `tickets.server.ts`. Note this file uses the **zod** validator form
(`tickets.server.ts`, `sessions.server.ts`), *not* the hand-rolled `raw: unknown` form used by
`customers.server.ts` — both exist in the tree, and the correct one to copy is the one belonging to
the pattern being reused. `zod` is already a dependency; **no `package.json` change.**

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type NotificationRow = {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  channel: string;
  template_code: string | null;
  status: string;
  sent_at: string | null;
  created_at: string | null;
};

export type NotificationIndex = {
  notifications: NotificationRow[];
  total: number;
  counts: Record<string, number>;
  limit: number;
  offset: number;
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  channel: z.string().trim().max(20).optional(),
  status: z.string().trim().max(20).optional(),
});

export const listNotifications = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data, context }) =>
    businessApi<NotificationIndex>("/api/v1/notifications", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.channel ? { channel: data.channel } : {}),
        ...(data.status ? { status: data.status } : {}),
      },
      role: context.session.role,
    }),
  );
```

### 4.5 `Frontend/admin_dashboard/src/lib/nexus/query-keys.ts`

Add a `notificationKeys` namespace immediately after `ticketKeys`. The file's own docstring says
*"Every cookbook adds its keys here, never inline."*

```ts
export const notificationKeys = {
  all: ["notifications"] as const,
  list: (channel: string, status: string, limit: number) =>
    ["notifications", "list", channel, status, limit] as const,
};
```

> **Match the adjacent block's style literally.** If the neighbouring `ticketKeys` object omits
> `as const`, omit it here too. This is the FEATURE_17 §6.4/§6.6 lesson applied in advance: when the
> printed snippet and the tree disagree on a stylistic detail, **the tree wins**.

### 4.6 `Frontend/admin_dashboard/src/lib/nexus/notification-view.ts` — new

```ts
import { formatBusinessTime } from "@/lib/nexus/callback-view";

/** D18.2 — billing.notifications.status is CHECK-constrained to queued/sent/failed, but only two
 *  are ever written: _persist passes "sent" or "failed", and the column default is 'sent'. There is
 *  no `sent` key in status.ts, so it maps onto `resolved` - the same mapping decision-view.ts's
 *  actionStatusKey already uses for `succeeded`. The default arm exists so an out-of-band value can
 *  never render a blank chip (the defect Features 1, 3 and 4 each hit). */
export function notificationStatusKey(status: string | null): string {
  switch (status) {
    case "sent":
      return "resolved";
    case "failed":
      return "failed";
    case "queued":
      return "queued";
    default:
      return "open";
  }
}

const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
};

export function channelLabel(channel: string | null): string {
  if (!channel) return "\u2014";
  return CHANNEL_LABELS[channel] ?? channel;
}

/** D18.3 — the five codes in notification_service/templates.py. template_code is a nullable
 *  String(80) with no CheckConstraint, so an unmapped code renders raw rather than being hidden. */
const TEMPLATE_LABELS: Record<string, string> = {
  advisor_callback: "Advisor callback",
  callback_scheduled: "Callback scheduled",
  ticket_created: "Ticket created",
  ticket_resolved: "Ticket resolved",
  ticket_updated: "Ticket updated",
};

export function templateLabel(template: string | null): string {
  if (!template) return "\u2014";
  return TEMPLATE_LABELS[template] ?? template;
}

/** D18.1 — customer_id is NULL for advisor-addressed sends (notify_advisor posts an empty
 *  customer_id, which to_uuid() turns into NULL) and for any non-UUID caller id. "Unattributed"
 *  is the honest word: the row is real, the recipient simply is not a row in crm.customers.
 *  A NULL customer and a customer we failed to join are different facts, so they read differently. */
export function notificationRecipient(name: string | null, customerId: string | null): string {
  const trimmed = name?.trim();
  if (trimmed) return trimmed;
  return customerId ? "Unknown customer" : "Unattributed";
}

export const STATUS_ORDER = ["sent", "failed", "queued"] as const;

export const STATUS_LABELS: Record<string, string> = {
  sent: "Sent",
  failed: "Failed",
  queued: "Queued",
};

/** Mirrors ticket-view.statusCount — counts omit zero-row statuses; never render a blank. */
export function statusCount(counts: Record<string, number> | undefined, status: string): number {
  return counts?.[status] ?? 0;
}

/** D18.5 — sourced from created_at, never sent_at. _persist does not set sent_at; the column's
 *  server_default fills it at INSERT even for failed rows, so it records when the attempt was
 *  logged, not when a message was delivered. Same reasoning as ticket-view's "Synced" column. */
export function notificationTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone ?? "UTC");
}
```

`formatBusinessTime` is the same helper `ticket-view.ts` imports from `callback-view`. **No bespoke
date formatter, no `toLocaleString`, no `new Date(`.**

### 4.7 `Frontend/admin_dashboard/src/routes/notifications.tsx` — new

A structural clone of `routes/tickets.tsx`. Every class string below appears in that file.

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { MailX } from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import { listNotifications } from "@/lib/api/notifications.server";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  channelLabel,
  notificationRecipient,
  notificationStatusKey,
  notificationTime,
  statusCount,
  templateLabel,
} from "@/lib/nexus/notification-view";
import { availabilityKeys, notificationKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";

const COLUMN_COUNT = 5;

const CHANNEL_OPTIONS = [
  { id: "", label: "All" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "sms", label: "SMS" },
  { id: "email", label: "Email" },
];

export const Route = createFileRoute("/notifications")({
  head: () => ({
    meta: [
      { title: "Notifications — Nexus" },
      {
        name: "description",
        content: "Outbound SMS, WhatsApp and email sends, with the channel and the outcome.",
      },
      { property: "og:title", content: "Notifications — Nexus" },
      { property: "og:description", content: "Every written confirmation the platform attempted." },
    ],
  }),
  component: NotificationsPage,
});

function NotificationsPage() {
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const [limit, setLimit] = useState(50);

  const notificationsQuery = useQuery({
    queryKey: notificationKeys.list(channel, status, limit),
    queryFn: () =>
      listNotifications({
        data: {
          limit,
          offset: 0,
          channel: channel || undefined,
          status: status || undefined,
        },
      }),
  });

  // F14 — business timezone; shared cache with /availability, /callbacks, /calls and /tickets.
  const coverageQuery = useQuery({
    queryKey: availabilityKeys.coverage(1),
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const rows = notificationsQuery.data?.notifications ?? [];
  const total = notificationsQuery.data?.total ?? 0;
  const counts = notificationsQuery.data?.counts;

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection>
        <Card>
          <div className="grid grid-cols-3 gap-sp-6">
            {STATUS_ORDER.map((key) => {
              const active = status === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStatus(active ? "" : key)}
                  className="text-left"
                  aria-pressed={active}
                >
                  <span className="t-micro block text-ink-5">{STATUS_LABELS[key]}</span>
                  <span
                    className={
                      active ? "t-metric-m block text-ink-1" : "t-metric-m block text-ink-3"
                    }
                  >
                    {formatInteger(statusCount(counts, key))}
                  </span>
                </button>
              );
            })}
          </div>
          {/* D18.4 / §2.5 — never let this read as "every message the platform sent". */}
          <p className="t-caption mt-sp-6 text-ink-5">
            Written by the notification-service after each send attempt. A failed row means the
            provider or the contact lookup refused it; the reason is returned to the caller but not
            stored, so it cannot be shown here. Times are when the attempt was logged.
            {!timeZone && !coverageQuery.isPending
              ? " Times shown in UTC — the business timezone could not be loaded."
              : null}
          </p>
        </Card>
      </PageSection>

      {/* ---------- Table ---------- */}
      <PageSection>
        <TableShell
          toolbar={
            <Segmented
              items={CHANNEL_OPTIONS.map((o) => o.label)}
              active={CHANNEL_OPTIONS.find((o) => o.id === channel)?.label ?? "All"}
              onSelect={(label) =>
                setChannel(CHANNEL_OPTIONS.find((o) => o.label === label)?.id ?? "")
              }
            />
          }
          head={
            <tr>
              <Th>Recipient</Th>
              <Th>Channel</Th>
              <Th>Template</Th>
              <Th>Status</Th>
              {/* D18.5 — "Logged", not "Sent": sent_at is a server default written at INSERT. */}
              <Th align="right">Logged</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                Showing {rows.length} of {formatInteger(total)} sends
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </>
          }
        >
          {notificationsQuery.isPending ? (
            <TableSkeleton columns={COLUMN_COUNT} rows={6} />
          ) : notificationsQuery.isError ? (
            <TableErrorRow
              columns={COLUMN_COUNT}
              error={notificationsQuery.error}
              onRetry={() => notificationsQuery.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <EmptyState
                  icon={MailX}
                  title="No notifications found"
                  description="No send attempt matches this filter."
                />
              </td>
            </tr>
          ) : (
            rows.map((n) => (
              <tr key={n.id} className="transition-colors duration-[120ms] hover:bg-surface-3">
                <Td>
                  <span className="flex items-center gap-sp-4">
                    <span className="truncate">
                      {notificationRecipient(n.customer_name, n.customer_id)}
                    </span>
                    {n.customer_vip ? <Token strong>VIP</Token> : null}
                  </span>
                </Td>
                <Td>
                  <Token mono={false}>{channelLabel(n.channel)}</Token>
                </Td>
                <Td>
                  <span className="t-ui truncate text-ink-1">{templateLabel(n.template_code)}</span>
                </Td>
                <Td>
                  <StatusChip status={notificationStatusKey(n.status)} />
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">
                    {notificationTime(n.created_at, timeZone)}
                  </span>
                </Td>
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>
    </>
  );
}
```

**G1/G2/G3 compliance:** no `SearchInput` is used (G1 moot); `Segmented` is label-keyed with
`items: string[]` + `active` + `onSelect`, copied from `tickets.tsx` (G2); the empty row uses a raw
`<td colSpan={COLUMN_COUNT}>` rather than `Td`, exactly as `tickets.tsx` does (G3).

**One class string differs from `tickets.tsx`:** `grid grid-cols-3 gap-sp-6` instead of
`grid grid-cols-2 gap-sp-6 md:grid-cols-5`. Only the column count changes, because there are three
statuses instead of five; the token set (`gap-sp-6`) and the utility family are unchanged. No
responsive breakpoint is needed for three tiles.

### 4.8 `Frontend/admin_dashboard/src/lib/nexus/nav.ts`

Three small edits to the existing file — no restructuring.

**(a)** Add `Send` to the existing `lucide-react` import block (it is the only new icon; `MailX` in
§4.7 is imported locally by the route, exactly as `tickets.tsx` imports `TicketX`).

```ts
  PhoneOutgoing,
  CalendarClock,
  Send,
  BarChart3,
```

**(b)** Add the destination to `NAV`, in the `OPERATIONS` section after `callbacks`:

```ts
  {
    id: "notifications",
    label: "Notifications",
    href: "/notifications",
    icon: Send,
    section: "OPERATIONS",
    shortcut: "G M",
  },
```

`OPERATIONS` is the right section: every template in `templates.py` is operational
(`ticket_*`, `callback_scheduled`, `advisor_callback`), and its siblings are `/calls`, `/advisors`,
`/availability`, `/callbacks` — the same operational loop.

`G M` ("messages") is free. In use: `G O C E T K P R L A D B J N G S`. `G N` is taken by Analytics.

**(c)** Add the `PAGE_META` entry, after `/callbacks`:

```ts
  "/notifications": {
    title: "Notifications",
    subtitle: "Written confirmations the platform attempted, and how they landed.",
  },
```

No badge is set. `badge` on `tickets` (42) and `callbacks` (7) are template leftovers; adding a
hardcoded count here would be inventing data.

### 4.9 `routeTree.gen.ts` — expect it to change, do not hand-edit

This is the **first cookbook in the 15-18 series to add a route file**, so it is also the first to
touch a generated file. The TanStack Router plugin regenerates
`Frontend/admin_dashboard/src/routeTree.gen.ts` on the next `npm run dev` or `npm run build`,
adding the `/notifications` route.

- **Do not edit it by hand.** Run the build and let the plugin write it.
- **It is a tracked file**, so `git status` will show it modified. That is expected and correct.
- Checklist item 20 ("`git diff --stat -- src/routes/` shows only FEATURE_15's `callbacks.tsx`") is
  **superseded for this cookbook**: it must now show `callbacks.tsx` **and** the new
  `notifications.tsx`. Item 21 covers `routeTree.gen.ts` separately.

---

## 5. Validation checklist

Run from the repo root unless noted. Use **`git grep`** — `rg` is absent from your PATH.

### Backend

| # | Check | Expected |
| --- | --- | --- |
| 1 | `python -m ruff check apps/business-api/src/business_api/repositories.py` | All checks passed (`Notification` sorted between `Invoice` and `Payment`) |
| 2 | `python -m ruff check apps/business-api/tests/test_notification_list.py` | All checks passed |
| 3 | `python -m ruff check apps/business-api/src/business_api/main.py` | **7 pre-existing** (I001 + 6x B904), count unchanged |
| 4 | `python -m pytest apps/business-api/tests -q` | **28 passed** (26 baseline + 2 new) |
| 5 | `git diff --stat -- services/ infra/ packages/` | empty — no migration, no writer change |
| 6 | `git diff -- apps/business-api/src/business_api/security.py` | empty (`require_role` factory reused) |
| 7 | `git grep -n "national_id" apps/business-api/src/business_api/repositories.py` | only the pre-existing `customer_list` docstring; no hit inside `notification_list` |
| 8 | `git grep -n "^from sqlalchemy" apps/business-api/src/business_api/repositories.py` | exactly one line, unchanged: `from sqlalchemy import func, or_, select` |
| 9 | `git diff -- apps/business-api/src/business_api/main.py` | one new handler; **no CORS hunk, no middleware hunk** |
| 10 | `docker compose … build business-api && docker compose … up -d business-api` | image rebuilt, container healthy (the Dockerfile bakes the source — rebuild, never restart) |

### Live route (rebuilt `business-api` on `:8108`)

| # | Check | Expected |
| --- | --- | --- |
| 11 | `curl -H "X-Role: superviseur" "…/api/v1/notifications?limit=5"` | `200`, shape `{notifications, total, counts, limit, offset}` |
| 12 | `curl -H "X-Role: conseiller" "…/api/v1/notifications"` | **`403 {"detail":"requires role >= superviseur"}"`** — one rank below |
| 13 | `curl -H "X-Role: superviseur" "…/api/v1/notifications?limit=0"` | `200` with `"limit": 1` (clamped, not a 422) |
| 14 | `curl -H "X-Role: superviseur" "…/api/v1/notifications?channel=carrier-pigeon"` | `200`, `notifications: []`, `total: 0` |
| 15 | `curl -H "X-Role: superviseur" "…/api/v1/notifications?status=failed"` | `200`; `counts` still shows the **global** breakdown (§4.1) |

> Item 12 is the one that differs from FEATURE_16/17. Those routes are `conseiller`, so `agent`
> was the 403 probe. This route is `superviseur`, so **`conseiller` is the correct 403 probe.**

### Frontend

| # | Check | Expected |
| --- | --- | --- |
| 16 | `node node_modules/typescript/bin/tsc --noEmit` | exit 0 |
| 17 | `npx eslint .` | 0 errors, **exactly 9** warnings (baseline preserved) |
| 18 | `npx prettier --write` on the touched files only — **never** `bun run format` | exit 0 |
| 19 | `npm run build` (client + SSR + nitro) | exit 0 |
| 20 | `git diff --stat -- src/routes/` | `callbacks.tsx` (FEATURE_15) **plus new `notifications.tsx`** — see §4.9 |
| 21 | `git diff --stat -- src/routeTree.gen.ts` | modified by the plugin, **not** hand-edited |
| 22 | `git diff -- src/lib/nexus/status.ts` | **empty** |
| 23 | `git diff --stat -- package.json` | empty — `zod`, `lucide-react` already present |
| 24 | `git grep -nE "rgb\(\|#[0-9a-fA-F]{3,6}" -- src/routes/notifications.tsx src/lib/nexus/notification-view.ts` | no hits |
| 25 | `git grep -nE "toLocaleString\(\|new Date\(\|getDay\(\|getHours\(" -- src/routes/notifications.tsx src/lib/nexus/notification-view.ts` | no hits (times go through `formatBusinessTime`) |
| 26 | every class string in `notifications.tsx` also appears in `routes/tickets.tsx` | true, with the single documented exception `grid grid-cols-3 gap-sp-6` (§4.7) |
| 27 | `StatusChip` renders non-blank for all three enum values | `sent`->`resolved`, `failed`->`failed`, `queued`->`queued`, default->`open` |
| 28 | `Td` is never given a `colSpan` | the empty row uses a raw `<td colSpan={COLUMN_COUNT}>` (G3) |
| 29 | Zero direct browser requests to `:8108` | by construction — server function -> `businessApi()` |
| 30 | Sidebar shows **Notifications** under OPERATIONS; `G M` navigates; topbar title/subtitle render | from `NAV` + `PAGE_META` |

### Manual end-to-end

31. Open `/notifications`. Three status tiles render; clicking **Failed** filters the table and the
    tiles keep their global counts (§4.1).
32. The channel `Segmented` filters to WhatsApp / SMS / Email and back to All.
33. A row whose `customer_id` is NULL reads **"Unattributed"**, not a blank cell and not a UUID.
34. **Generate a live row**, which is the honest end-to-end proof for this feature: open a ticket
    through the agent so `glpi_ticket_ops.create_ticket` posts to `/notify` with
    `template: "ticket_created"`. Then:
    ```sql
    SELECT channel, template_code, status, sent_at FROM billing.notifications ORDER BY sent_at DESC;
    ```
    (this exact query is the one `docs/persistence/PERSISTENCE-P5-README.md` already documents).
    The new row must appear at the top of the page.
35. If the notification-service is running **without** `DATABASE_URL`, no row is written at all
    (§2.5). Confirm the variable is set in that container before concluding the page is broken.

---

## 6. Ambiguities and decisions needing your confirmation

**A. Standalone page vs. a tenth section in the 360 modal.** *(Recommended: standalone page.)*
The evidence for a page is §2.3: advisor sends carry `customer_id = NULL` and would be structurally
invisible in a per-customer modal, and the modal is already at nine sections after FEATURE_17. The
cost is that this is the first cookbook in the series to add a nav destination and to touch the
generated `routeTree.gen.ts`. If you would rather not grow the sidebar right now, the alternative is
a `customer_id`-filtered section in the modal — but I would then have to state plainly that the page
hides a category of rows, which I do not think you want.

**B. Is `notify_advisor` actually called anywhere?** *(Needs your local `git grep` — §2.3.)*
GitHub's code search returned 0 hits for the token even though the method exists in a file I read,
so the index is untrustworthy here and I will not guess. If it turns out to have **no** callers, then
`advisor_callback` rows never appear and the "Unattributed" case reduces to non-UUID caller ids only
— the code is unchanged either way, but I would soften the caption. Please run:
`git grep -n "notify_advisor\|advisor_callback" -- apps/ services/ mcp-servers/`

**C. Add `template` and `customer_id` filters now, or leave them out?** *(Recommended: leave out.)*
Both are ~3 lines each in the repository, the route, and the server function. I left them out because
nothing in this cookbook's UI consumes them, and unwired query parameters are dead surface. Say the
word and I will add a second `Segmented` for template — `tickets.tsx` already carries a 6-option
`Segmented`, so there is exact precedent for the control.

**D. The discarded failure reason — queue it as FEATURE_19?** *(Recommended: queue, do not build.)*
§2.4: `NotifyResponse.reason` holds the real cause and is thrown away before the INSERT. Capturing it
needs a new column on `billing.Notification`, an Alembic migration, and a two-line change in
`_persist` — which is a **write-path change in a locked directory**, so it is out of bounds for this
series under constraint 2/3. It is, however, the single highest-value follow-up here: without it,
"8 failed" is a number nobody can act on.

**E. What closes out the projections/unexposed-table sweep?** After this, `billing.Account` is the
only untouched table with a writer, and it is already implied by the invoices shown in the 360 modal
(account-level fields are `account_number`, `billing_cycle_day`, `payment_terms_days`, `status`).
My read is that it is worth a **small** cookbook only if you want dunning status visible; otherwise
the sweep is done and the backlog reverts to the three carried-forward items: the **"Total invoiced"
mislabel** correction, the **C12 "Attributed turns"** relabel, and writing **D13** (the shared
`POLICY_*` file requirement) into the deploy docs.

---







FEATURE_18_notification_log.md is above.
The writer check came first, and it passed
FEATURE_16 killed CustomerInteraction for having zero writers, so I ran the same test before writing a line. billing.Notification has a real one: NotificationService._persist in services/notification-service/src/notification_service/service.py, plus its own migration 0005_ticketing_notifications.py. The service docstring is explicit that failures are recorded, not swallowed:
"Live-only, no mock fallback. If a channel is unconfigured or the provider rejects the message, sent=False is returned with the actual reason. The DB record is written with status='failed'."
So a failed row is a real refusal. Three distinct failure modes — no contact handle, channel unconfigured, provider rejection — all land there.
One finding changed the entire shape of the feature
notify_advisor() posts "customer_id": "", and to_uuid("") returns None rather than raising. Advisor pages are therefore stored with customer_id = NULL. Non-UUID caller ids (the service's own test uses "TT-100021") do the same.
That rules out a tenth section in the 360 modal: it would structurally hide an entire category of rows. This is a standalone /notifications page under OPERATIONS, superviseur per the BATCH_1_APPLY §1 role invariant, cloned from /tickets.
Three things I refused to do
sent_at is not rendered as "Sent." _persist never sets it — the column's server_default now() fills it at INSERT, including for failed rows. The column is labelled "Logged" from created_at, following the precedent /tickets already set with Synced, not Updated.
The failure reason is flagged, not built. NotifyResponse.reason holds the real cause and is discarded before the INSERT. Capturing it needs a new column + migration in packages/persistence — a write-path change in a locked directory. §6-D.
counts stay globally unfiltered, because ticket_list computes them that way and the tiles are filter toggles. I matched the behaviour rather than "improving" it into an inconsistency.
One thing I could not verify and did not guess
search_code "notify_advisor" returned 0 hits — for a method I had just read in notification_client.py. GitHub's index is unreliable for that token, so I won't assert callers exist or don't. §6-B asks you to run git grep -n "notify_advisor\|advisor_callback" locally; the code is correct either way, only the caption wording depends on it.
Two heads-ups before you apply
This is the first cookbook in the 15–18 series to add a route file and a nav destination, so routeTree.gen.ts will regenerate — expected, tracked, and must not be hand-edited (§4.9). And the 403 probe changes: this route is superviseur, so conseiller is the correct one-rank-below probe, not agent.
Baseline moves 26 → 28; neither new test inserts a row, per the national_id lesson. All six of your FEATURE_17 adaptations are pre-applied and listed in §7.




## 7. Conventions this cookbook commits to

Carried forward from the FEATURE_17 corrections, applied here in advance:

| Convention | Applied at |
| --- | --- |
| `self._s`, never `self.session` | §4.1 |
| `-> dict`, never `-> dict[str, Any]` | §4.2 |
| `role: SuperviseurRole` named, never `_:` | §4.2 |
| Validator shape copied from the pattern being reused (zod here, per `tickets.server.ts`) | §4.4 |
| Null-guard every timestamp helper at the call site | `notificationTime` accepts `string \| null` by signature — §4.6 |
| When the snippet and the tree disagree on style, **the tree wins** | stated inline at §4.5 |
| No bare `Customer(...)` in tests (`national_id` is `nullable=False`) | §4.3 — no inserts at all |
| Backend route ⇒ `docker compose build business-api && up -d` | §5 item 10 |
| `git grep`, never `rg` | §5 preamble |



