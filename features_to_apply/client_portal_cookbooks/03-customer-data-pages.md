# COOKBOOK 3 — CUSTOMER DATA PAGES (+ ADDITIVE `/api/v1/me/*`)

**Backend touched:** one **new** file (`me_reads.py`) and one **append-only** block in `main.py`. No existing function, model, projection, or migration is modified. `repositories.py` is never opened.
**New dependencies:** none. **No migration.** **No writes.**

---

## 3.0 What already exists, and therefore is not rebuilt

| Portal need | Already shipped | Verdict |
|---|---|---|
| Identity, contact, address, locale, plan, MSISDN, account number, VIP, customer-since | `GET /api/v1/me/profile/detail` → `me_profile_detail`, 16 fields | **use as-is**; `/profile` already does |
| Subscriptions (`msisdn`, `plan`, `status`), unpaid invoices (`invoice`, `amount`, `outstanding`, `status`), tickets (`glpi_id`, `status`, `subject`), `open_tickets` count | `GET /api/v1/me/profile` → `customer_360` | **use as-is** → Services “YOUR PLAN” and the Billing “amount due” hero need **no new endpoint** |

This is the single biggest correction to the attached `version_90` document: it planned a new subscriptions endpoint that is not needed.

---

## 3.1 Endpoints this cookbook adds (8 reads)

| Method | Path | Backs |
|---|---|---|
| GET | `/api/v1/me/sessions` | `/security` → active devices + `password_changed_at` |
| GET | `/api/v1/me/conversations` | `/activity` list (paginated) |
| GET | `/api/v1/me/conversations/{session_id}` | `/activity` transcript panel |
| GET | `/api/v1/me/requests` | `/requests` list (paginated) |
| GET | `/api/v1/me/billing` | `/billing` postpaid: accounts + invoices + payments |
| GET | `/api/v1/me/balance` | `/billing` prepaid: OCS balances + recharges |
| GET | `/api/v1/me/notifications` | topbar tray + `/activity` |
| GET | `/api/v1/me/callbacks` | `/activity` callbacks tab |

All eight are `ClientPrincipal`-gated, read-only, unaudited, and derive `customer_id` from the principal.

---

## 3.2 New backend file — `apps/business-api/src/business_api/me_reads.py`

Deliberately a **new module**: `repositories.py` stays byte-identical, so no advisor-facing behaviour can regress. Projections mirror the house style of `repositories.py` (plain dicts, ISO strings via `.isoformat()`, `float(...)` for `Numeric`, hard limit clamps).

```python
"""Client-scoped read projections for the customer portal.

Every function here is additive. None of them is used by an advisor route, and
none of them widens an existing projection: the advisor surface keeps returning
exactly what it returned before.

Invariants enforced by construction:
  * customer_id always arrives from Principal.customer_id (current_client),
    never from a path, query, or body parameter.
  * every {id} lookup re-checks ownership and returns None on a miss, so the
    route can answer 404 instead of leaking existence through a 403.
  * internal supervision signals never appear here: no frustration score, no
    sentiment, no recording URL, no consent flag, no notification failure
    reason, no token digest, no VIP flag, no GLPI sync timestamp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models.billing import Account, Invoice, Notification, Payment
from persistence.models.conversation import CallbackSchedule, CallSession, Turn
from persistence.models.crm import Subscription
from persistence.models.ocs import BalanceAccount, Recharge
from persistence.models.portal_identity import PortalAccount, PortalSession
from persistence.models.ticketing import Ticket

# Same ceilings as repositories.py so one surface cannot be used to sweep more
# rows than the other.
_PAGE_MAX = 50
_LIST_MAX = 200
_TURN_MAX = 400


def _page(limit: int | None, offset: int | None) -> tuple[int, int]:
    size = min(max(int(limit or 20), 1), _PAGE_MAX)
    start = max(int(offset or 0), 0)
    return size, start


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _num(value: Decimal | float | int | None) -> float | None:
    return float(value) if value is not None else None


def _subscription_ids(session: Session, customer_id: UUID) -> list[UUID]:
    """Every subscription belonging to this customer. The only bridge used to
    reach OCS balances, which are keyed by subscription and not by customer."""
    return list(
        session.scalars(
            select(Subscription.subscription_id).where(
                Subscription.customer_id == customer_id
            )
        ).all()
    )


# --------------------------------------------------------------------------
# /me/sessions
# --------------------------------------------------------------------------
def portal_sessions(
    session: Session,
    *,
    account_id: UUID,
    current_session_id: UUID | None,
) -> dict[str, Any]:
    """Live sign-ins for the caller's own portal account.

    token_digest is never selected. A row is 'active' when it is neither
    revoked nor expired, which is the same predicate portal_auth uses when it
    validates a bearer token.
    """
    now = datetime.now(timezone.utc)

    rows = session.execute(
        select(
            PortalSession.session_id,
            PortalSession.created_at,
            PortalSession.expires_at,
            PortalSession.ip_address,
            PortalSession.user_agent,
        )
        .where(
            PortalSession.account_id == account_id,
            PortalSession.revoked_at.is_(None),
            PortalSession.expires_at > now,
        )
        .order_by(PortalSession.created_at.desc())
        .limit(_LIST_MAX)
    ).all()

    password_changed_at = session.scalar(
        select(PortalAccount.password_changed_at).where(
            PortalAccount.account_id == account_id
        )
    )

    return {
        "password_changed_at": _iso(password_changed_at),
        "sessions": [
            {
                "session_id": str(row.session_id),
                "signed_in_at": _iso(row.created_at),
                "expires_at": _iso(row.expires_at),
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "current": current_session_id is not None
                and row.session_id == current_session_id,
            }
            for row in rows
        ],
    }


# --------------------------------------------------------------------------
# /me/conversations
# --------------------------------------------------------------------------
def conversations(
    session: Session,
    *,
    customer_id: UUID,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Call history for this customer.

    Narrower than repositories.session_list on purpose: max_frustration,
    recording_consent, and has_recording are supervision signals and stay out.
    """
    size, start = _page(limit, offset)

    total = session.scalar(
        select(func.count())
        .select_from(CallSession)
        .where(CallSession.customer_id == customer_id)
    )

    turn_counts = (
        select(Turn.session_id, func.count().label("turns"))
        .group_by(Turn.session_id)
        .subquery()
    )

    rows = session.execute(
        select(
            CallSession.session_id,
            CallSession.channel,
            CallSession.start_time,
            CallSession.end_time,
            CallSession.duration_seconds,
            CallSession.final_disposition,
            func.coalesce(turn_counts.c.turns, 0).label("turns"),
        )
        .outerjoin(turn_counts, turn_counts.c.session_id == CallSession.session_id)
        .where(CallSession.customer_id == customer_id)
        .order_by(CallSession.start_time.desc())
        .limit(size)
        .offset(start)
    ).all()

    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": [
            {
                "session_id": str(row.session_id),
                "channel": row.channel,
                "started_at": _iso(row.start_time),
                "ended_at": _iso(row.end_time),
                "duration_seconds": row.duration_seconds,
                "disposition": row.final_disposition,
                "turns": int(row.turns),
            }
            for row in rows
        ],
    }


def conversation_detail(
    session: Session,
    *,
    customer_id: UUID,
    session_id: UUID,
) -> dict[str, Any] | None:
    """Masked transcript for one of this customer's own calls.

    Ownership is part of the WHERE clause, so another customer's session_id is
    indistinguishable from a nonexistent one: both return None -> 404.

    Compared with repositories.session_detail this drops max_frustration and
    the whole sentiment array, and drops detected_intent per turn.
    """
    head = session.execute(
        select(
            CallSession.session_id,
            CallSession.channel,
            CallSession.start_time,
            CallSession.end_time,
            CallSession.duration_seconds,
            CallSession.final_disposition,
        ).where(
            CallSession.session_id == session_id,
            CallSession.customer_id == customer_id,
        )
    ).one_or_none()

    if head is None:
        return None

    turns = session.execute(
        select(
            Turn.turn_index,
            Turn.speaker,
            Turn.active_agent,
            Turn.detected_language,
            Turn.transcript_masked,
            Turn.created_at,
        )
        .where(Turn.session_id == session_id)
        .order_by(Turn.turn_index.asc(), Turn.speaker.asc())
        .limit(_TURN_MAX)
    ).all()

    return {
        "session_id": str(head.session_id),
        "channel": head.channel,
        "started_at": _iso(head.start_time),
        "ended_at": _iso(head.end_time),
        "duration_seconds": head.duration_seconds,
        "disposition": head.final_disposition,
        "turns": [
            {
                "index": row.turn_index,
                "speaker": row.speaker,
                "agent": row.active_agent,
                "language": row.detected_language,
                "text": row.transcript_masked,
                "at": _iso(row.created_at),
            }
            for row in turns
        ],
    }


# --------------------------------------------------------------------------
# /me/requests
# --------------------------------------------------------------------------
def requests(
    session: Session,
    *,
    customer_id: UUID,
    status: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Support tickets raised for this customer.

    Narrower than repositories.ticket_list: customer_vip and last_synced_at are
    operational metadata and stay out.
    """
    size, start = _page(limit, offset)

    conditions = [Ticket.customer_id == customer_id]
    if status:
        conditions.append(Ticket.status == status)

    total = session.scalar(
        select(func.count()).select_from(Ticket).where(*conditions)
    )

    rows = session.execute(
        select(
            Ticket.ticket_id,
            Ticket.glpi_ticket_id,
            Ticket.category,
            Ticket.subject,
            Ticket.status,
            Ticket.priority,
            Ticket.created_at,
            Ticket.updated_at,
        )
        .where(*conditions)
        .order_by(Ticket.created_at.desc())
        .limit(size)
        .offset(start)
    ).all()

    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": [
            {
                "reference": row.glpi_ticket_id,
                "category": row.category,
                "subject": row.subject,
                "status": row.status,
                "priority": row.priority,
                "created_at": _iso(row.created_at),
                "updated_at": _iso(row.updated_at),
            }
            for row in rows
        ],
    }


# --------------------------------------------------------------------------
# /me/billing  (postpaid / hybrid)
# --------------------------------------------------------------------------
def billing(session: Session, *, customer_id: UUID) -> dict[str, Any]:
    """Billing accounts, their invoices, and settled payments.

    repositories.customer_ledger returns payments, payment plans, and consents
    but no invoices, so the invoice list is built here directly over
    billing.invoices. Nothing in customer_ledger changes.
    """
    accounts = session.execute(
        select(
            Account.account_id,
            Account.account_number,
            Account.account_type,
            Account.billing_cycle_day,
            Account.currency_code,
            Account.status,
        )
        .where(Account.customer_id == customer_id)
        .order_by(Account.created_at.asc())
    ).all()

    account_ids = [row.account_id for row in accounts]

    invoices: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []

    if account_ids:
        invoice_rows = session.execute(
            select(
                Invoice.invoice_id,
                Invoice.account_id,
                Invoice.invoice_number,
                Invoice.period_start,
                Invoice.period_end,
                Invoice.issue_date,
                Invoice.due_date,
                Invoice.subtotal,
                Invoice.tax_amount,
                Invoice.total_amount,
                Invoice.outstanding_amount,
                Invoice.currency_code,
                Invoice.status,
            )
            .where(Invoice.account_id.in_(account_ids))
            .order_by(Invoice.issue_date.desc())
            .limit(_LIST_MAX)
        ).all()

        invoices = [
            {
                "invoice_number": row.invoice_number,
                "account_number": next(
                    (a.account_number for a in accounts if a.account_id == row.account_id),
                    None,
                ),
                "period_start": _iso(row.period_start),
                "period_end": _iso(row.period_end),
                "issue_date": _iso(row.issue_date),
                "due_date": _iso(row.due_date),
                "subtotal": _num(row.subtotal),
                "tax_amount": _num(row.tax_amount),
                "total_amount": _num(row.total_amount),
                "outstanding_amount": _num(row.outstanding_amount),
                "currency_code": row.currency_code,
                "status": row.status,
            }
            for row in invoice_rows
        ]

        payment_rows = session.execute(
            select(
                Payment.payment_id,
                Payment.amount,
                Payment.currency_code,
                Payment.method,
                Payment.status,
                Payment.paid_at,
                Invoice.invoice_number,
            )
            .join(Invoice, Invoice.invoice_id == Payment.invoice_id, isouter=True)
            .where(Payment.account_id.in_(account_ids))
            .order_by(Payment.paid_at.desc().nullslast())
            .limit(_LIST_MAX)
        ).all()

        payments = [
            {
                "amount": _num(row.amount),
                "currency_code": row.currency_code,
                "method": row.method,
                "status": row.status,
                "paid_at": _iso(row.paid_at),
                "invoice_number": row.invoice_number,
            }
            for row in payment_rows
        ]

    total_outstanding = sum(
        (item["outstanding_amount"] or 0.0)
        for item in invoices
        if item["status"] not in {"paid", "void"}
    )

    return {
        "accounts": [
            {
                "account_number": row.account_number,
                "account_type": row.account_type,
                "billing_cycle_day": row.billing_cycle_day,
                "currency_code": row.currency_code,
                "status": row.status,
            }
            for row in accounts
        ],
        "total_outstanding": round(float(total_outstanding), 2),
        "currency_code": (accounts[0].currency_code if accounts else "TND"),
        "invoices": invoices,
        "payments": payments,
    }


# --------------------------------------------------------------------------
# /me/balance  (prepaid)
# --------------------------------------------------------------------------
def balance(session: Session, *, customer_id: UUID) -> dict[str, Any]:
    """OCS balances per subscription plus recent recharges.

    The same tables repositories.customer_service_actions already reads, kept to
    a narrower projection and split out so the portal never calls the advisor
    route. transaction_reference is not exposed.
    """
    subscription_ids = _subscription_ids(session, customer_id)
    if not subscription_ids:
        return {"balances": [], "recharges": []}

    balance_rows = session.execute(
        select(
            BalanceAccount.subscription_id,
            BalanceAccount.balance_type,
            BalanceAccount.balance_value,
            BalanceAccount.balance_unit,
            BalanceAccount.expiry_date,
            BalanceAccount.status,
            Subscription.msisdn,
        )
        .join(
            Subscription,
            Subscription.subscription_id == BalanceAccount.subscription_id,
        )
        .where(BalanceAccount.subscription_id.in_(subscription_ids))
        .order_by(Subscription.msisdn.asc(), BalanceAccount.balance_type.asc())
    ).all()

    recharge_rows = session.execute(
        select(
            Recharge.amount,
            Recharge.bonus_amount,
            Recharge.channel,
            Recharge.status,
            Recharge.created_at,
            Subscription.msisdn,
        )
        .join(
            Subscription,
            Subscription.subscription_id == Recharge.subscription_id,
        )
        .where(Recharge.subscription_id.in_(subscription_ids))
        .order_by(Recharge.created_at.desc())
        .limit(_PAGE_MAX)
    ).all()

    return {
        "balances": [
            {
                "msisdn": row.msisdn,
                "balance_type": row.balance_type,
                "value": _num(row.balance_value),
                "unit": row.balance_unit,
                "expires_on": _iso(row.expiry_date),
                "status": row.status,
            }
            for row in balance_rows
        ],
        "recharges": [
            {
                "msisdn": row.msisdn,
                "amount": _num(row.amount),
                "bonus_amount": _num(row.bonus_amount),
                "channel": row.channel,
                "status": row.status,
                "created_at": _iso(row.created_at),
            }
            for row in recharge_rows
        ],
    }


# --------------------------------------------------------------------------
# /me/notifications
# --------------------------------------------------------------------------
def notifications(
    session: Session,
    *,
    customer_id: UUID,
    limit: int | None = None,
) -> dict[str, Any]:
    """Messages the platform sent to this customer.

    repositories.notification_list is deliberately not customer-scoped and it
    returns failure_reason, which can carry gateway detail. This read is scoped
    and drops failure_reason entirely: a customer is told a message failed, not
    why an SMS gateway rejected it.
    """
    size, _ = _page(limit, 0)

    rows = session.execute(
        select(
            Notification.notification_id,
            Notification.channel,
            Notification.template_code,
            Notification.status,
            Notification.sent_at,
            Notification.created_at,
        )
        .where(Notification.customer_id == customer_id)
        .order_by(Notification.created_at.desc())
        .limit(size)
    ).all()

    return {
        "items": [
            {
                "channel": row.channel,
                "template_code": row.template_code,
                "status": row.status,
                "sent_at": _iso(row.sent_at),
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }


# --------------------------------------------------------------------------
# /me/callbacks
# --------------------------------------------------------------------------
def callbacks(
    session: Session,
    *,
    customer_id: UUID,
    limit: int | None = None,
) -> dict[str, Any]:
    """Scheduled call-backs for this customer. outcome_note is an advisor note
    and is not exposed; attempts is an operational counter and is not exposed.
    """
    size, _ = _page(limit, 0)

    rows = session.execute(
        select(
            CallbackSchedule.callback_id,
            CallbackSchedule.scheduled_time,
            CallbackSchedule.preferred_window,
            CallbackSchedule.status,
            CallbackSchedule.reason,
            CallbackSchedule.completed_at,
        )
        .where(CallbackSchedule.customer_id == customer_id)
        .order_by(CallbackSchedule.scheduled_time.desc())
        .limit(size)
    ).all()

    return {
        "items": [
            {
                "scheduled_time": _iso(row.scheduled_time),
                "preferred_window": row.preferred_window,
                "status": row.status,
                "reason": row.reason,
                "completed_at": _iso(row.completed_at),
            }
            for row in rows
        ]
    }
```

### Preflight for this file (run before writing it)

```sh
# Confirm the exact class + column names used above.
git grep -n "class Subscription" -A 30 -- packages/persistence/src/persistence/models/crm.py
git grep -n "class Payment"      -A 25 -- packages/persistence/src/persistence/models/billing.py
sed -n '1,80p' packages/persistence/src/persistence/base.py     # Timestamps -> created_at / updated_at
```

If `Payment` has no `account_id` (i.e. it hangs off `invoice_id` only), drop the `Payment.account_id.in_(...)` filter and join through `Invoice` instead — the projection stays identical, and remove the now-unused import or `ruff` fails on `F401`. If `Ticket` has no `updated_at`, remove that key from the projection and from the TS type; the UI already tolerates `null` there.

---

## 3.3 `main.py` — the append-only route block

Insert **immediately before `def run()`** at the end of the file. Nothing above it moves.

```python
# ---------------------------------------------------------------------------
# Client self-service reads (customer portal).
#
# Additive by construction:
#   * every route is gated by ClientPrincipal -> current_client, which refuses
#     staff and machine principals;
#   * customer_id and account_id come from the principal, never from the
#     request, so there is no client-supplied identifier to tamper with;
#   * every path parameter is re-checked against the caller's customer_id and
#     answers 404 on a miss, so existence is not leaked through 403;
#   * reads are not audited, matching every other read route in this file;
#   * projections live in me_reads.py and no advisor projection was widened.
# ---------------------------------------------------------------------------


@app.get("/api/v1/me/sessions", tags=["me"])
def me_sessions(
    principal: ClientPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    if principal.account_id is None:
        raise HTTPException(status_code=403, detail="requires a portal account")
    return me_reads.portal_sessions(
        db,
        account_id=principal.account_id,
        current_session_id=principal.session_id,
    )


@app.get("/api/v1/me/conversations", tags=["me"])
def me_conversations(
    principal: ClientPrincipal,
    db: DbSession,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    return me_reads.conversations(
        db,
        customer_id=principal.customer_id,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/me/conversations/{session_id}", tags=["me"])
def me_conversation_detail(
    session_id: UUID,
    principal: ClientPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    payload = me_reads.conversation_detail(
        db,
        customer_id=principal.customer_id,
        session_id=session_id,
    )
    if payload is None:
        # 404, not 403: a conversation belonging to someone else must be
        # indistinguishable from one that does not exist.
        raise HTTPException(status_code=404, detail="conversation not found")
    return payload


@app.get("/api/v1/me/requests", tags=["me"])
def me_requests(
    principal: ClientPrincipal,
    db: DbSession,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    return me_reads.requests(
        db,
        customer_id=principal.customer_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/me/billing", tags=["me"])
def me_billing(
    principal: ClientPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    return me_reads.billing(db, customer_id=principal.customer_id)


@app.get("/api/v1/me/balance", tags=["me"])
def me_balance(
    principal: ClientPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    return me_reads.balance(db, customer_id=principal.customer_id)


@app.get("/api/v1/me/notifications", tags=["me"])
def me_notifications(
    principal: ClientPrincipal,
    db: DbSession,
    limit: int = 20,
) -> dict[str, Any]:
    return me_reads.notifications(
        db,
        customer_id=principal.customer_id,
        limit=limit,
    )


@app.get("/api/v1/me/callbacks", tags=["me"])
def me_callbacks(
    principal: ClientPrincipal,
    db: DbSession,
    limit: int = 20,
) -> dict[str, Any]:
    return me_reads.callbacks(
        db,
        customer_id=principal.customer_id,
        limit=limit,
    )
```

And exactly one import line added to the existing import block:

```diff
 from business_api import me_reads
```

> `UUID`, `HTTPException`, `Any`, `DbSession`, and `ClientPrincipal` are already imported in `main.py` (verified). Add nothing else.

---

## 3.4 Frontend server functions

One file per domain, each mirroring the verified `me.server.ts` idiom (`createServerFn` + `authedMiddleware` + `businessApi`).

**Add** `src/lib/api/activity.server.ts`:

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

export type Paged<T> = { total: number; limit: number; offset: number; items: T[] };

export type ConversationSummary = {
  session_id: string;
  channel: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  disposition: string | null;
  turns: number;
};

export type ConversationTurn = {
  index: number;
  speaker: "caller" | "agent";
  agent: string | null;
  language: string | null;
  text: string | null;
  at: string | null;
};

export type ConversationDetail = Omit<ConversationSummary, "turns"> & {
  turns: ConversationTurn[];
};

export const fetchConversations = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      limit: z.number().int().min(1).max(50).default(10),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) =>
    businessApi<Paged<ConversationSummary>>(
      `/api/v1/me/conversations?limit=${data.limit}&offset=${data.offset}`,
    ),
  );

export const fetchConversation = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(z.object({ sessionId: z.string().uuid() }))
  .handler(({ data }) =>
    businessApi<ConversationDetail>(
      `/api/v1/me/conversations/${encodeURIComponent(data.sessionId)}`,
    ),
  );

export type CallbackItem = {
  scheduled_time: string | null;
  preferred_window: string | null;
  status: "pending" | "completed" | "cancelled";
  reason: string | null;
  completed_at: string | null;
};

export const fetchCallbacks = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<{ items: CallbackItem[] }>("/api/v1/me/callbacks?limit=20"));
```

**Add** `src/lib/api/requests.server.ts`:

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";
import type { Paged } from "./activity.server";

/** ticketing.tickets CHECK constraint — five values, not four. */
export const TICKET_STATUSES = [
  "open",
  "in_progress",
  "pending",
  "resolved",
  "closed",
] as const;
export type TicketStatus = (typeof TICKET_STATUSES)[number];

export type RequestItem = {
  reference: string;
  category: "network_complaint" | "formal_complaint" | "technical" | "billing" | "other";
  subject: string | null;
  status: TicketStatus;
  priority: "low" | "medium" | "high" | "urgent" | null;
  created_at: string | null;
  updated_at: string | null;
};

export const fetchRequests = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .validator(
    z.object({
      status: z.enum(TICKET_STATUSES).optional(),
      limit: z.number().int().min(1).max(50).default(10),
      offset: z.number().int().min(0).default(0),
    }),
  )
  .handler(({ data }) => {
    const params = new URLSearchParams({
      limit: String(data.limit),
      offset: String(data.offset),
    });
    if (data.status) params.set("status", data.status);
    return businessApi<Paged<RequestItem>>(`/api/v1/me/requests?${params.toString()}`);
  });
```

**Add** `src/lib/api/billing.server.ts`:

```ts
import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

export type BillingAccount = {
  account_number: string;
  account_type: "postpaid" | "hybrid";
  billing_cycle_day: number | null;
  currency_code: string;
  status: string;
};

export type InvoiceItem = {
  invoice_number: string;
  account_number: string | null;
  period_start: string | null;
  period_end: string | null;
  issue_date: string | null;
  due_date: string | null;
  subtotal: number | null;
  tax_amount: number | null;
  total_amount: number | null;
  outstanding_amount: number | null;
  currency_code: string;
  status: "draft" | "issued" | "paid" | "partial" | "overdue" | "disputed" | "void";
};

export type PaymentItem = {
  amount: number | null;
  currency_code: string;
  method: string | null;
  status: string;
  paid_at: string | null;
  invoice_number: string | null;
};

export type BillingPayload = {
  accounts: BillingAccount[];
  total_outstanding: number;
  currency_code: string;
  invoices: InvoiceItem[];
  payments: PaymentItem[];
};

export type BalanceItem = {
  msisdn: string | null;
  balance_type: "main" | "data" | "voice" | "sms";
  value: number | null;
  unit: "TND" | "GB" | "MB" | "MIN" | "SMS";
  expires_on: string | null;
  status: "active" | "expired" | "suspended";
};

export type RechargeItem = {
  msisdn: string | null;
  amount: number | null;
  bonus_amount: number | null;
  channel: "app" | "web" | "ussd" | "scratch_card" | "agent";
  status: "pending" | "completed" | "failed";
  created_at: string | null;
};

export type BalancePayload = { balances: BalanceItem[]; recharges: RechargeItem[] };

export const fetchBilling = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<BillingPayload>("/api/v1/me/billing"));

export const fetchBalance = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<BalancePayload>("/api/v1/me/balance"));
```

**Add** `src/lib/api/notifications.server.ts`:

```ts
import { createServerFn } from "@tanstack/react-start";
import { businessApi } from "./business-api";
import { authedMiddleware } from "./middleware";

export type NotificationItem = {
  channel: "sms" | "whatsapp" | "email";
  template_code: string | null;
  status: "queued" | "sent" | "failed";
  sent_at: string | null;
  created_at: string | null;
};

export const fetchNotifications = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() =>
    businessApi<{ items: NotificationItem[] }>("/api/v1/me/notifications?limit=20"),
  );
```

**Append** to `src/lib/api/account.server.ts` (created in Cookbook 2):

```ts
export type PortalSessionItem = {
  session_id: string;
  signed_in_at: string | null;
  expires_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
  current: boolean;
};

export type PortalSessionsPayload = {
  password_changed_at: string | null;
  sessions: PortalSessionItem[];
};

export const fetchPortalSessions = createServerFn({ method: "GET" })
  .middleware([authedMiddleware])
  .handler(() => businessApi<PortalSessionsPayload>("/api/v1/me/sessions"));
```

---

## 3.5 Presentation helpers — TND, `Africa/Tunis`, safe label maps

**Add** `src/lib/format.ts`. Every number, date, and enum goes through this file; no component formats anything itself.

```ts
/**
 * lib/format.ts — one formatter for the whole portal.
 *
 * Currency is TND (billing.accounts.currency_code defaults to 'TND') and the
 * operational timezone is Africa/Tunis (CALLBACK_TIMEZONE in the backend).
 * Locale is en-GB so dates read 16 August 2026, matching the existing copy deck.
 */
const LOCALE = "en-GB";
export const TIME_ZONE = "Africa/Tunis";

export function money(value: number | null | undefined, currency = "TND"): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 3, // TND is a 3-decimal currency (millimes)
  }).format(value);
}

export function quantity(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "—";
  if (unit === "TND") return money(value);
  const formatted = new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: unit === "GB" ? 2 : 0,
  }).format(value);
  return `${formatted} ${unit}`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

/** "3 minutes ago", "2 days ago" — last-active and last-changed rows. */
export function relative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const deltaSeconds = Math.round((then - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const steps: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, seconds] of steps) {
    if (Math.abs(deltaSeconds) >= seconds) {
      return rtf.format(Math.round(deltaSeconds / seconds), unit);
    }
  }
  return rtf.format(deltaSeconds, "second");
}

/** duration_seconds -> "4m 18s". Replaces the hardcoded value on /assistant. */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0 ? `${minutes}m ${String(rest).padStart(2, "0")}s` : `${rest}s`;
}

/**
 * Device line for /security, derived from user_agent (max 200 chars in the DB).
 * Deliberately coarse: no UA parsing library, no fingerprinting, and an unknown
 * agent is labelled honestly rather than guessed at.
 */
export function deviceLabel(userAgent: string | null): string {
  if (!userAgent) return "Unknown device";
  const ua = userAgent.toLowerCase();
  const os = ua.includes("iphone")
    ? "iPhone"
    : ua.includes("ipad")
      ? "iPad"
      : ua.includes("android")
        ? "Android"
        : ua.includes("mac os")
          ? "Mac"
          : ua.includes("windows")
            ? "Windows"
            : ua.includes("linux")
              ? "Linux"
              : "Unknown device";
  const browser = ua.includes("edg/")
    ? "Edge"
    : ua.includes("chrome/") && !ua.includes("chromium")
      ? "Chrome"
      : ua.includes("firefox/")
        ? "Firefox"
        : ua.includes("safari/")
          ? "Safari"
          : "Browser";
  return `${browser} on ${os}`;
}
```

**Modify** `src/lib/copy.ts` — the label maps that keep raw enum values off the screen. These are the exact DB enums:

```ts
  labels: {
    // conversation.call_sessions.final_disposition
    disposition: {
      resolved: "Resolved",
      escalated: "Passed to a specialist",
      dropped: "Disconnected",
      abandoned: "Ended early",
    },
    channel: { voice: "Voice", whatsapp: "WhatsApp", web: "Web", chat: "Chat" },
    // ticketing.tickets.status — five values (copy.requests.status had four)
    requestStatus: {
      open: "Received",
      in_progress: "In progress",
      pending: "Waiting on us",
      resolved: "Resolved",
      closed: "Closed",
    },
    requestCategory: {
      network_complaint: "Network",
      formal_complaint: "Formal complaint",
      technical: "Technical",
      billing: "Billing",
      other: "Other",
    },
    priority: { low: "Low", medium: "Medium", high: "High", urgent: "Urgent" },
    invoiceStatus: {
      draft: "Draft",
      issued: "Issued",
      paid: "Paid",
      partial: "Partly paid",
      overdue: "Overdue",
      disputed: "Disputed",
      void: "Cancelled",
    },
    balanceType: { main: "Credit", data: "Data", voice: "Calls", sms: "Texts" },
    rechargeChannel: {
      app: "App",
      web: "Web",
      ussd: "USSD",
      scratch_card: "Scratch card",
      agent: "In store",
    },
    notificationChannel: { sms: "Text message", whatsapp: "WhatsApp", email: "Email" },
    notificationStatus: { queued: "Queued", sent: "Sent", failed: "Not delivered" },
    callbackStatus: { pending: "Scheduled", completed: "Done", cancelled: "Cancelled" },
    speaker: { caller: "You", agent: "Assistant" },
  },
```

> Unknown enum values must degrade, never crash. Always read them as
> `copy.labels.requestStatus[status] ?? status`.

---

## 3.6 Notification tray — the honest replacement for D‑9

`billing.notifications` has **no read/unread column**, so the topbar’s unread dot cannot be computed and must go. The tray becomes a short “recent messages” list.

* rows are `channel + template_code → human sentence`, `status`, and `sent_at ?? created_at`;
* `template_code` is an internal code (e.g. `invoice_ready`) — never render it raw; map through `copy.notificationTemplates` with a `genericMessage` fallback;
* `failed` renders as “Not delivered” with **no** reason;
* empty tray keeps `copy.shell.notificationsEmpty` (“Nothing new.”);
* the dot is removed entirely, not faked with “newer than the last visit”.

```ts
  notificationTemplates: {
    // Extend as templates appear; unknown codes fall back to genericMessage.
    invoice_ready: "Your invoice is ready",
    payment_received: "We received your payment",
    payment_failed: "A payment did not go through",
    plan_changed: "Your plan was changed",
    ticket_update: "An update on one of your requests",
    callback_scheduled: "We scheduled a call back",
  },
  notifications: {
    heading: "RECENT MESSAGES",
    genericMessage: "A message about your account",
    empty: "Nothing new.",
  },
```

---

## 3.7 Page wiring, screen by screen

| Screen | Endpoint(s) | Sections after wiring |
|---|---|---|
| `/security` | `fetchPortalSessions` | **Sign-in**: `copy.security.lastChanged(relative(password_changed_at))` or `lastChangedNever` + change-password panel (CB2). **Active sessions**: `deviceLabel(user_agent)`, `ip_address`, `relative(signed_in_at)`, `current` → chip “This device”, one “Sign out of every device” action. **Recent activity**: derived from the same sign-in list — do **not** invent a security-event feed; a real one is a new read over `audit.*` and belongs in a later cookbook |
| `/activity` | `fetchConversations`, `fetchRequests`, `fetchCallbacks` | hero = most recent conversation (`dateTime`, `duration`, `turns`, disposition chip); tabs All / Conversations / Requests / Callbacks; paginated list (CB4); row click opens the transcript panel via `fetchConversation` |
| `/requests` | `fetchRequests` | status tabs from the **five** DB statuses (Active = `open,in_progress,pending`); rows show `reference`, `subject ?? category label`, status chip, `dateTime(created_at)`; detail panel read-only — no reply box |
| `/services` | `fetchProfileDetail` + `fetchBalance` | **YOUR PLAN** from `customer_360.subscriptions` (`plan`, `msisdn`, `status`) — no new endpoint; usage `Meter` **only** for prepaid data balances, with `overNote={copy.services.overAllowance}`; add-ons deleted (CB1) |
| `/billing` | `fetchBilling`, `fetchBalance` | if `accounts.length > 0`: **AMOUNT DUE** (`money(total_outstanding, currency_code)`) + invoice table (`invoice_number`, period, `due_date`, `money(total_amount)`, status chip) + payments list. If `accounts.length === 0`: prepaid layout — balance cards per `msisdn`/`balance_type` with `quantity(value, unit)` and `expires_on`, plus recharge history. Payment-method card and PDF actions deleted (CB1) |
| topbar | `fetchNotifications` | tray per §3.6; no unread dot |
| `/profile` | unchanged | already correct — the reference implementation |

**Hybrid accounts are real** (`account_type ∈ {postpaid, hybrid}`) and can have both invoices and OCS balances. Render whichever list is non-empty; never assume mutual exclusivity.

---

## 3.8 Query keys and caching

TanStack Query is already a dependency. Key everything by customer so signing in as a different account cannot show stale data:

```ts
export const qk = {
  profileDetail: (cid: string) => ["me", cid, "profile-detail"] as const,
  profile360: (cid: string) => ["me", cid, "profile"] as const,
  sessions: (cid: string) => ["me", cid, "sessions"] as const,
  conversations: (cid: string, limit: number, offset: number) =>
    ["me", cid, "conversations", limit, offset] as const,
  conversation: (cid: string, id: string) => ["me", cid, "conversation", id] as const,
  requests: (cid: string, status: string | undefined, limit: number, offset: number) =>
    ["me", cid, "requests", status ?? "all", limit, offset] as const,
  billing: (cid: string) => ["me", cid, "billing"] as const,
  balance: (cid: string) => ["me", cid, "balance"] as const,
  notifications: (cid: string) => ["me", cid, "notifications"] as const,
  callbacks: (cid: string) => ["me", cid, "callbacks"] as const,
};
```

`cid` is `session.customerId` from the cookie (Cookbook 2 §2.2) — a cache key only, never sent upstream. `staleTime: 30_000` for lists; `placeholderData: keepPreviousData` for paginated lists so page changes do not blank the layout (Cookbook 4 depends on this).

---

## 3.9 Verification

### Backend, with a real client token

```sh
TOKEN=$(curl -s -X POST localhost:8108/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"test-client-403@example.tn","password":"client-secret-test-55"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')

for p in sessions conversations requests billing balance notifications callbacks; do
  printf '%-16s ' "$p"
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
    "localhost:8108/api/v1/me/$p"
done
```

All seven must be `200`. Then the isolation tests — these are the ones that matter:

```sh
# 1. Another customer's conversation must be 404, never 200 and never 403.
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  localhost:8108/api/v1/me/conversations/00000000-0000-0000-0000-000000000000

# 2. A staff token must be refused by every /me route.
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $STAFF" \
  localhost:8108/api/v1/me/billing    # expect 403

# 3. The machine principal must be refused too.
curl -s -o /dev/null -w '%{http_code}\n' -H "X-API-Key: $INTERNAL_API_KEY" \
  localhost:8108/api/v1/me/billing    # expect 403

# 4. No leak check: none of these words may appear in any /me payload.
for p in conversations requests billing balance notifications callbacks; do
  curl -s -H "Authorization: Bearer $TOKEN" "localhost:8108/api/v1/me/$p" \
  | grep -Eo 'frustration|sentiment|token_digest|failure_reason|audio_record_url|recording_consent|customer_vip|last_synced_at|outcome_note|transaction_reference' \
  && echo "LEAK in /me/$p" && exit 1
done; echo "no leaks"
```

### Advisor-surface non-regression (proves “additive”)

```sh
git diff --stat version_92 -- apps/business-api/src/business_api/repositories.py   # must be empty
git diff        version_92 -- apps/business-api/src/business_api/main.py | grep '^-' | grep -v '^---'  # must be empty
ls packages/persistence/alembic/versions | wc -l   # unchanged
```

Then re-run the advisor smoke calls (`/api/v1/customers`, `/customers/{id}/360`, `/tickets`, `/sessions`, `/notifications`) with a conseiller token and diff the payloads against `version_92`. They must be byte-identical.

### Frontend

| # | Check |
|---|---|
| 1 | `git grep -n "lib/fixtures" -- Frontend/customer_portal/src` returns only `interactions.ts` consumers (removed in CB5) |
| 2 | Every amount on `/billing` reads `TND`: `git grep -n '£\|\$[0-9]' -- Frontend/customer_portal/src` → empty |
| 3 | A prepaid-only customer (Yousra Trabelsi, CIN `9912`) sees balance cards and **no** empty postpaid shell |
| 4 | A postpaid customer (Amine Ben Salah, `4087`, `BA-000021`) sees invoices with outstanding amounts |
| 5 | `/security` shows exactly one “This device” chip; a second browser adds a row |
| 6 | No raw enum on screen: `git grep -n 'in_progress\|network_complaint\|scratch_card' -- Frontend/customer_portal/src/routes` returns only label-map lookups |
| 7 | A customer with no history gets `EmptyState`, not a skeleton that never resolves |

### Rollback

Delete `me_reads.py`, revert the `main.py` block and the one import line, revert the frontend commit. No schema, no data, no existing route touched.
