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

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
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


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _num(value: Decimal | float | int | None) -> float | None:
    return float(value) if value is not None else None


def _subscription_ids(session: Session, customer_id: UUID) -> list[UUID]:
    """Every subscription belonging to this customer. The only bridge used to
    reach OCS balances, which are keyed by subscription and not by customer."""
    return list(
        session.scalars(
            select(Subscription.id).where(
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
    now = datetime.now(UTC)

    rows = session.execute(
        select(
            PortalSession.id,
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
            PortalAccount.id == account_id
        )
    )

    return {
        "password_changed_at": _iso(password_changed_at),
        "sessions": [
            {
                "session_id": str(row.id),
                "signed_in_at": _iso(row.created_at),
                "expires_at": _iso(row.expires_at),
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "current": current_session_id is not None
                and row.id == current_session_id,
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
            CallSession.id,
            CallSession.channel,
            CallSession.start_time,
            CallSession.end_time,
            CallSession.duration_seconds,
            CallSession.final_disposition,
            func.coalesce(turn_counts.c.turns, 0).label("turns"),
        )
        .outerjoin(turn_counts, turn_counts.c.session_id == CallSession.id)
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
                "session_id": str(row.id),
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
            CallSession.id,
            CallSession.channel,
            CallSession.start_time,
            CallSession.end_time,
            CallSession.duration_seconds,
            CallSession.final_disposition,
        ).where(
            CallSession.id == session_id,
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
        .order_by(Turn.turn_index.asc(), Turn.created_at.asc())
        .limit(_TURN_MAX)
    ).all()

    return {
        "session_id": str(head.id),
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
    operational metadata and stay out. `updated_at` (migration 0021) is not:
    the portal renders "when did this last change" on the request panel and in
    Activity, and until that column existed both screens printed an em dash.
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
            Ticket.id,
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


# Statuses that owe nothing.
_EXCLUDED_OUTSTANDING = ("paid", "void")


# --------------------------------------------------------------------------
# /me/billing  (postpaid / hybrid)
# --------------------------------------------------------------------------
def billing(
    session: Session,
    *,
    customer_id: UUID,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Billing accounts, their invoices, and settled payments.

    repositories.customer_ledger returns payments, payment plans, and consents
    but no invoices, so the invoice list is built here directly over
    billing.invoices. Nothing in customer_ledger changes.
    """
    accounts = session.execute(
        select(
            Account.id,
            Account.account_number,
            Account.account_type,
            Account.billing_cycle_day,
            Account.currency_code,
            Account.status,
        )
        .where(Account.customer_id == customer_id)
        .order_by(Account.created_at.asc())
    ).all()

    account_ids = [row.id for row in accounts]

    invoices: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []

    size, start = _page(limit, offset)

    if not account_ids:
        return {
            "accounts": [],
            "total_outstanding": 0.0,
            "next_due_date": None,
            "currency_code": "",
            "invoices": {"total": 0, "limit": size, "offset": start, "items": []},
            "payments": [],
        }

    # Whole-account figures must not follow the invoice page: an outstanding
    # balance or a next-due date computed from 20 visible rows would misstate
    # what is owed and when.
    totals_stmt = select(
        func.count(Invoice.id),
        func.coalesce(
            func.sum(
                case(
                    (
                        Invoice.status.notin_(_EXCLUDED_OUTSTANDING),
                        Invoice.outstanding_amount,
                    ),
                    else_=0,
                )
            ),
            0,
        ),
        # Earliest due date still owing, across every account invoice.
        func.min(
            case(
                (
                    Invoice.status.notin_(_EXCLUDED_OUTSTANDING),
                    Invoice.due_date,
                ),
                else_=None,
            )
        ),
    ).where(Invoice.account_id.in_(account_ids))
    invoice_total, outstanding_sum, next_due_date = session.execute(totals_stmt).one()

    invoice_rows = session.execute(
        select(
            Invoice.id,
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
        .offset(start)
        .limit(size)
    ).all()

    payment_rows = session.execute(
        select(
            Payment.id,
            Payment.amount,
            Payment.currency_code,
            Payment.method,
            Payment.status,
            Payment.paid_at,
            Invoice.invoice_number,
        )
        .join(Invoice, Invoice.id == Payment.invoice_id, isouter=True)
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

    currency_code = accounts[0].currency_code if accounts else ""

    invoices = [
        {
            "invoice_number": row.invoice_number,
            "account_number": next(
                (a.account_number for a in accounts if a.id == row.account_id),
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
        # Account-wide, deliberately independent of the invoice page below.
        "total_outstanding": _num(outstanding_sum) or 0.0,
        "next_due_date": _iso(next_due_date),
        "currency_code": currency_code,
        "invoices": {
            "total": int(invoice_total or 0),
            "limit": size,
            "offset": start,
            "items": invoices,
        },
        # Payments stay a short unpaged recent list: they are context for the
        # invoices, not a browsable ledger. Capped by _LIST_MAX as before.
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
            Subscription.id == BalanceAccount.subscription_id,
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
            Subscription.id == Recharge.subscription_id,
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
    offset: int | None = None,
) -> dict[str, Any]:
    """Messages the platform sent to this customer.

    repositories.notification_list is deliberately not customer-scoped and it
    returns failure_reason, which can carry gateway detail. This read is scoped
    and drops failure_reason entirely: a customer is told a message failed, not
    why an SMS gateway rejected it.
    """
    size, start = _page(limit, offset)

    total = session.scalar(
        select(func.count(Notification.id)).where(
            Notification.customer_id == customer_id
        )
    )

    rows = session.execute(
        select(
            Notification.id,
            Notification.channel,
            Notification.template_code,
            Notification.status,
            Notification.sent_at,
            Notification.created_at,
        )
        .where(Notification.customer_id == customer_id)
        .order_by(Notification.created_at.desc(), Notification.id.asc())
        .offset(start)
        .limit(size)
    ).all()

    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": [
            {
                "channel": row.channel,
                "template_code": row.template_code,
                "status": row.status,
                "sent_at": _iso(row.sent_at),
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ],
    }


# --------------------------------------------------------------------------
# /me/callbacks
# --------------------------------------------------------------------------
def callbacks(
    session: Session,
    *,
    customer_id: UUID,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """Scheduled call-backs for this customer. outcome_note is an advisor note
    and is not exposed; attempts is an operational counter and is not exposed.
    """
    size, start = _page(limit, offset)

    total = session.scalar(
        select(func.count(CallbackSchedule.id)).where(
            CallbackSchedule.customer_id == customer_id
        )
    )

    rows = session.execute(
        select(
            CallbackSchedule.id,
            CallbackSchedule.scheduled_time,
            CallbackSchedule.preferred_window,
            CallbackSchedule.status,
            CallbackSchedule.reason,
            CallbackSchedule.completed_at,
        )
        .where(CallbackSchedule.customer_id == customer_id)
        .order_by(CallbackSchedule.scheduled_time.desc(), CallbackSchedule.id.asc())
        .offset(start)
        .limit(size)
    ).all()

    return {
        "total": int(total or 0),
        "limit": size,
        "offset": start,
        "items": [
            {
                "scheduled_time": _iso(row.scheduled_time),
                "preferred_window": row.preferred_window,
                "status": row.status,
                "reason": row.reason,
                "completed_at": _iso(row.completed_at),
            }
            for row in rows
        ],
    }
