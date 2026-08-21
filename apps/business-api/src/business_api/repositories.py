"""Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."""
from __future__ import annotations

import os
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from business_api.kpis import Kpis, compute_kpis
from persistence.models.billing import Account, Invoice, Notification, Payment, PaymentPlan
from persistence.models.conversation import (
    AgentUsageEvent,
    CallSession,
    EscalationCase,
    SentimentSample,
    Turn,
)
from persistence.models.crm import ConsentRecord, Customer, Subscription
from persistence.models.execution import ActionLedger
from persistence.models.ocs import BalanceAccount, Recharge
from persistence.models.policy import PolicyVerdict
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder
from persistence.models.reference import BusinessRule, ErrorCatalog, GeoArea, Product, RechargeCatalog
from persistence.models.sim import BlockUnblockCase
from persistence.models.ticketing import Ticket
from persistence.util import to_uuid

# Payments, deferral plans and consent captures per customer (FEATURE_16). A hard cap keeps
# the modal's read cheap; the UI surfaces "latest 50" when a collection is full.
_LEDGER_LIMIT = 50

# Live balances, plan history and service-action projections per customer (FEATURE_17).
_SERVICE_LIMIT = 50

# Outbound notification send log (FEATURE_18). A hard cap mirrors ticket_list's own clamp.
_NOTIFICATION_LIMIT_MAX = 200

# Escalation queue (spec section 17.6). A hard cap keeps the handoff read cheap; the UI
# surfaces "latest 200" when the queue is full.
_ESCALATION_LIMIT = 200


class SupervisionRepository:
    """Back-office reads over the persisted platform data."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def customer_360(self, customer_id: str) -> dict | None:
        cid = to_uuid(customer_id)
        customer = self._s.get(Customer, cid) if cid else None
        if customer is None:
            return None
        subs = self._s.scalars(select(Subscription).where(Subscription.customer_id == cid)).all()
        invoices = self._s.scalars(select(Invoice).where(Invoice.customer_id == cid)).all()
        tickets = self._s.scalars(select(Ticket).where(Ticket.customer_id == cid)).all()
        return {
            "customer_id": str(customer.id),
            "name": f"{customer.first_name} {customer.last_name}",
            "vip": customer.vip_flag,
            "preferred_language": customer.preferred_language,
            "subscriptions": [
                {"subscription_id": str(s.id), "msisdn": s.msisdn, "plan": s.plan_code or s.plan_type, "status": s.status}
                for s in subs
            ],
            "open_invoices": [
                {
                    "invoice": i.invoice_number,
                    "amount": float(i.total_amount),
                    # FEATURE_21 — additive key (same precedent as the C13 keys on escalations()).
                    # `amount` is the invoice face value; `outstanding` is what is still owed.
                    # Both columns are NOT NULL with server_default 0, so neither needs a guard.
                    "outstanding": float(i.outstanding_amount),
                    "status": i.status,
                }
                for i in invoices if i.status != "paid"
            ],
            "tickets": [{"glpi_id": t.glpi_ticket_id, "status": t.status, "subject": t.subject} for t in tickets],
        }

    def customer_ledger(self, customer_id: str) -> dict | None:
        """Payments, deferral plans and consent captures for one customer.

        Deliberately a separate method from `customer_360`: widening that method's
        return shape would change existing behaviour for every existing caller.
        Returns None when the customer does not exist, so the route can 404 the
        same way `/360` does.
        """
        cid = to_uuid(customer_id)
        customer = self._s.execute(
            select(Customer).where(Customer.id == cid)
        ).scalar_one_or_none()
        if customer is None:
            return None

        payments = (
            self._s.execute(
                select(Payment)
                .where(Payment.customer_id == cid)
                .order_by(Payment.created_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )
        plans = (
            self._s.execute(
                select(PaymentPlan)
                .where(PaymentPlan.customer_id == cid)
                .order_by(PaymentPlan.created_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )
        consents = (
            self._s.execute(
                select(ConsentRecord)
                .where(ConsentRecord.customer_id == cid)
                .order_by(ConsentRecord.captured_at.desc())
                .limit(_LEDGER_LIMIT)
            )
            .scalars()
            .all()
        )

        # Batched invoice-number lookup, mirroring the `customers = {...}` pattern
        # used by ticket_list/session_list. Never one query per payment.
        invoice_ids = {p.invoice_id for p in payments if p.invoice_id is not None}
        invoice_numbers: dict = {}
        if invoice_ids:
            invoice_numbers = {
                row.id: row.invoice_number
                for row in self._s.execute(
                    select(Invoice).where(Invoice.id.in_(invoice_ids))
                ).scalars()
            }

        return {
            "customer_id": str(customer.id),
            "payments": [
                {
                    "payment_id": str(p.id),
                    "amount": float(p.amount),
                    "currency_code": p.currency_code,
                    "method": p.method,
                    "status": p.status,
                    "gateway_reference": p.gateway_reference,
                    "invoice": invoice_numbers.get(p.invoice_id),
                    "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in payments
            ],
            "payment_plans": [
                {
                    "plan_id": str(pl.id),
                    "total_amount": float(pl.total_amount),
                    "installment_count": pl.installment_count,
                    "installment_amount": float(pl.installment_amount),
                    "deferral_until": pl.deferral_until.isoformat() if pl.deferral_until else None,
                    "status": pl.status,
                    "policy_verdict_id": str(pl.policy_verdict_id) if pl.policy_verdict_id else None,
                    "created_at": pl.created_at.isoformat() if pl.created_at else None,
                }
                for pl in plans
            ],
            "consents": [
                {
                    "consent_id": str(c.id),
                    "consent_type": c.consent_type,
                    "granted": bool(c.granted),
                    "language": c.language,
                    "session_id": str(c.session_id),
                    "captured_at": c.captured_at.isoformat() if c.captured_at else None,
                }
                for c in consents
            ],
        }

    def me_profile_detail(self, customer_id: str) -> dict:
        """Profile fields for the signed-in client's own record.

        Deliberately a separate method from `customer_360`: widening that method's return shape
        would change existing behaviour for every existing caller. `national_id` is never
        selected - the CIN is tokenised in audit.pii_token_map and must not reach a browser.
        """
        cid = to_uuid(customer_id)
        customer = self._s.get(Customer, cid) if cid else None
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
            "status": customer.status,
            "plan": (subscription.plan_code or subscription.plan_type) if subscription else None,
            "msisdn": subscription.msisdn if subscription else None,
        }

    def customer_service_actions(self, customer_id: str) -> dict | None:
        """Live balances, plan history and service-action projections for one customer.

        Separate from customer_360/customer_ledger for the same reason as FEATURE_16:
        widening an existing method's return shape changes existing behaviour.

        Two of these tables (sim.block_unblock_cases, provisioning.plan_change_history)
        carry no customer_id, and two more allow it to be NULL, so everything is scoped
        through the customer's live subscriptions.
        """
        cid = to_uuid(customer_id)
        customer = self._s.execute(
            select(Customer).where(Customer.id == cid)
        ).scalar_one_or_none()
        if customer is None:
            return None

        subscriptions = list(
            self._s.execute(
                select(Subscription).where(
                    Subscription.customer_id == cid,
                    Subscription.deleted_at.is_(None),
                )
            ).scalars()
        )
        sub_ids = [s.id for s in subscriptions]
        msisdn_by_sub = {s.id: s.msisdn for s in subscriptions}

        # Tables with a nullable/absent customer_id must also be reachable by line.
        recharge_scope = Recharge.customer_id == cid
        sim_order_scope = SimOrder.customer_id == cid
        provisioning_scope = ProvisioningRequest.customer_id == cid
        if sub_ids:
            recharge_scope = or_(recharge_scope, Recharge.subscription_id.in_(sub_ids))
            sim_order_scope = or_(sim_order_scope, SimOrder.subscription_id.in_(sub_ids))
            provisioning_scope = or_(
                provisioning_scope, ProvisioningRequest.subscription_id.in_(sub_ids)
            )

        balances: list[BalanceAccount] = []
        plan_changes: list[PlanChangeHistory] = []
        sim_cases: list[BlockUnblockCase] = []
        if sub_ids:
            balances = list(
                self._s.execute(
                    select(BalanceAccount)
                    .where(BalanceAccount.subscription_id.in_(sub_ids))
                    .order_by(BalanceAccount.balance_type.asc())
                ).scalars()
            )
            plan_changes = list(
                self._s.execute(
                    select(PlanChangeHistory)
                    .where(PlanChangeHistory.subscription_id.in_(sub_ids))
                    .order_by(PlanChangeHistory.created_at.desc())
                    .limit(_SERVICE_LIMIT)
                ).scalars()
            )
            sim_cases = list(
                self._s.execute(
                    select(BlockUnblockCase)
                    .where(BlockUnblockCase.subscription_id.in_(sub_ids))
                    .order_by(BlockUnblockCase.created_at.desc())
                    .limit(_SERVICE_LIMIT)
                ).scalars()
            )

        recharges = list(
            self._s.execute(
                select(Recharge)
                .where(recharge_scope)
                .order_by(Recharge.created_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )
        sim_orders = list(
            self._s.execute(
                select(SimOrder)
                .where(sim_order_scope)
                .order_by(SimOrder.created_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )
        provisioning_rows = list(
            self._s.execute(
                select(ProvisioningRequest)
                .where(provisioning_scope)
                .order_by(ProvisioningRequest.requested_at.desc())
                .limit(_SERVICE_LIMIT)
            ).scalars()
        )

        events: list[dict] = []
        for row in recharges:
            events.append({
                "event_id": str(row.id),
                "source": "recharge",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id),
                "msisdn": msisdn_by_sub.get(row.subscription_id),
                "reference": row.transaction_reference,
                "amount": float(row.amount),
                "bonus_amount": float(row.bonus_amount),
                "channel": row.channel,
            })
        for row in sim_cases:
            events.append({
                "event_id": str(row.id),
                "source": "sim_case",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id),
                "msisdn": msisdn_by_sub.get(row.subscription_id),
                "reference": None,
                "action": row.action,
            })
        for row in sim_orders:
            events.append({
                "event_id": str(row.id),
                "source": "sim_order",
                "status": row.status,
                "occurred_at": row.created_at.isoformat() if row.created_at else None,
                "subscription_id": str(row.subscription_id) if row.subscription_id else None,
                "msisdn": msisdn_by_sub.get(row.subscription_id) if row.subscription_id else None,
                "reference": row.tracking_code,
                "sim_type": row.sim_type,
            })
        for row in provisioning_rows:
            events.append({
                "event_id": str(row.id),
                "source": "provisioning",
                "status": row.status,
                "occurred_at": row.requested_at.isoformat() if row.requested_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "subscription_id": str(row.subscription_id) if row.subscription_id else None,
                "msisdn": msisdn_by_sub.get(row.subscription_id) if row.subscription_id else None,
                "reference": None,
                "action_type": row.action_type,
            })

        # All four timestamps are tz-aware UTC isoformat strings, so lexicographic
        # ordering is chronological. Rows with no timestamp sort last.
        events.sort(key=lambda event: event["occurred_at"] or "", reverse=True)

        return {
            "customer_id": str(customer.id),
            "balances": [
                {
                    "balance_id": str(b.id),
                    "subscription_id": str(b.subscription_id),
                    "msisdn": msisdn_by_sub.get(b.subscription_id),
                    "balance_type": b.balance_type,
                    "balance_value": float(b.balance_value),
                    "balance_unit": b.balance_unit,
                    "status": b.status,
                    "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                    "updated_at": b.updated_at.isoformat() if b.updated_at else None,
                }
                for b in balances
            ],
            "plan_changes": [
                {
                    "change_id": str(c.id),
                    "subscription_id": str(c.subscription_id) if c.subscription_id else None,
                    "msisdn": msisdn_by_sub.get(c.subscription_id) if c.subscription_id else None,
                    "from_plan": c.from_plan,
                    "to_plan": c.to_plan,
                    "changed_by": c.changed_by,
                    "effective_date": c.effective_date.isoformat() if c.effective_date else None,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in plan_changes
            ],
            "events": events[:_SERVICE_LIMIT],
        }

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
                "failure_reason": r.failure_reason,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return {
            "notifications": items, "total": total, "counts": counts,
            "limit": limit, "offset": offset,
        }

    def customer_list(
        self,
        search: str = "",
        status: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """Paginated CRM registry for the admin dashboard (read-only).

        Deliberately does not select ``national_id``: the CIN is tokenised elsewhere
        (audit.pii_token_map) and must never reach a browser. Search therefore matches
        name / email / phone only.
        """
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))

        conditions = []
        conditions.append(Customer.deleted_at.is_(None))

        if status:
            conditions.append(Customer.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Customer.first_name.ilike(pattern),
                    Customer.last_name.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.contact_number.ilike(pattern),
                )
            )

        total = self._s.scalar(
            select(func.count()).select_from(Customer).where(*conditions)
        ) or 0

        rows = self._s.scalars(
            select(Customer)
            .where(*conditions)
            .order_by(Customer.last_name.asc(), Customer.first_name.asc())
            .limit(limit)
            .offset(offset)
        ).all()

        return {
            "customers": [
                {
                    "customer_id": str(c.id),
                    "name": f"{c.first_name} {c.last_name}".strip(),
                    "email": c.email,
                    "contact_number": c.contact_number,
                    "preferred_language": c.preferred_language,
                    "segment": c.segment,
                    "vip": bool(c.vip_flag),
                    "fraud_suspected": bool(c.fraud_suspected),
                    "status": c.status,
                    "city": c.city,
                }
                for c in rows
            ],
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }

    def ticket_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        customer_id: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Paginated view over the local GLPI mirror (ticketing.tickets).

        Read-only. GLPI remains the source of truth; this exposes the durable local projection
        the mirror was built to serve, and reports last_synced_at so the reader can judge how
        fresh that projection is.
        """
        stmt = select(Ticket)
        count_stmt = select(func.count()).select_from(Ticket)

        def _both(clause):
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if status:
            _both(Ticket.status == status)
        if category:
            _both(Ticket.category == category)
        if priority:
            _both(Ticket.priority == priority)

        cid = to_uuid(customer_id) if customer_id else None
        if cid is not None:
            _both(Ticket.customer_id == cid)

        if search:
            like = f"%{search.strip()}%"
            _both(Ticket.subject.ilike(like) | Ticket.glpi_ticket_id.ilike(like))

        total = self._s.scalar(count_stmt) or 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        rows = self._s.scalars(
            stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
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
                select(Ticket.status, func.count()).group_by(Ticket.status)
            ).all()
        }

        items = []
        for r in rows:
            customer = customers.get(r.customer_id)
            items.append({
                "ticket_id": r.glpi_ticket_id,
                "status": r.status,
                "subject": r.subject,
                "category": r.category,
                "priority": r.priority,
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "customer_name": f"{customer.first_name} {customer.last_name}".strip() if customer else None,
                "customer_vip": bool(customer.vip_flag) if customer else False,
                "subscription_id": str(r.subscription_id) if r.subscription_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                # Administrator note (migration 0020). Additive: existing consumers ignore the
                # extra keys, and every ticket without a note reports null exactly as before.
                "admin_note": r.admin_note,
                "note_author": r.note_author,
                "note_updated_at": r.note_updated_at.isoformat() if r.note_updated_at else None,
            })

        return {"tickets": items, "total": total, "counts": counts, "limit": limit, "offset": offset}

    def session_detail(self, session_id: str) -> dict | None:
        sid = to_uuid(session_id)
        call = self._s.get(CallSession, sid) if sid else None
        if call is None:
            return None
        turns = self._s.scalars(select(Turn).where(Turn.session_id == sid).order_by(Turn.turn_index)).all()
        sentiment = self._s.scalars(
            select(SentimentSample).where(SentimentSample.session_id == sid).order_by(SentimentSample.turn_index)
        ).all()
        return {
            "session_id": str(call.id),
            "disposition": call.final_disposition,
            "duration_seconds": call.duration_seconds,
            "max_frustration": float(call.max_frustration_score),
            "turns": [
                {"index": t.turn_index, "speaker": t.speaker, "agent": t.active_agent, "text": t.transcript_masked}
                for t in turns
            ],
            "sentiment": [{"index": x.turn_index, "score": float(x.score), "label": x.label} for x in sentiment],
        }

    def session_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        disposition: str | None = None,
        customer_id: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Paginated index of call sessions for the supervision dashboard.

        Read-only, like every method here. Exposes columns that are already persisted; it
        computes nothing the platform does not already know.
        """
        stmt = select(CallSession)
        count_stmt = select(func.count()).select_from(CallSession)

        if disposition:
            stmt = stmt.where(CallSession.final_disposition == disposition)
            count_stmt = count_stmt.where(CallSession.final_disposition == disposition)

        cid = to_uuid(customer_id) if customer_id else None
        if cid is not None:
            stmt = stmt.where(CallSession.customer_id == cid)
            count_stmt = count_stmt.where(CallSession.customer_id == cid)

        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(CallSession.msisdn.ilike(like))
            count_stmt = count_stmt.where(CallSession.msisdn.ilike(like))

        total = self._s.scalar(count_stmt) or 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        # start_time is nullable on in-flight rows; fall back to created_at so ordering is total.
        ordering = func.coalesce(CallSession.start_time, CallSession.created_at).desc()
        rows = self._s.scalars(stmt.order_by(ordering).limit(limit).offset(offset)).all()

        customer_ids = {r.customer_id for r in rows if r.customer_id}
        customers = {}
        if customer_ids:
            customers = {
                c.id: c
                for c in self._s.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
            }

        turn_counts: dict = {}
        if rows:
            turn_counts = dict(
                self._s.execute(
                    select(Turn.session_id, func.count())
                    .where(Turn.session_id.in_([r.id for r in rows]))
                    .group_by(Turn.session_id)
                ).all()
            )

        items = []
        for r in rows:
            customer = customers.get(r.customer_id)
            items.append({
                "session_id": str(r.id),
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "customer_name": f"{customer.first_name} {customer.last_name}".strip() if customer else None,
                "customer_vip": bool(customer.vip_flag) if customer else False,
                "preferred_language": customer.preferred_language if customer else None,
                "msisdn": r.msisdn,
                "channel": r.channel,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "duration_seconds": r.duration_seconds,
                "disposition": r.final_disposition,
                "max_frustration": (
                    float(r.max_frustration_score) if r.max_frustration_score is not None else None
                ),
                "recording_consent": bool(r.recording_consent),
                "has_recording": bool(r.audio_record_url),
                "turn_count": int(turn_counts.get(r.id, 0)),
            })

        return {"sessions": items, "total": total, "limit": limit, "offset": offset}

    def _project_escalation_cases(self, cases: list[EscalationCase]) -> list[dict]:
        """Customer identity for a batch of escalation cases.

        Precedence: the case's own customer_id wins; otherwise the call session's
        customer_id; otherwise null. Batched lookups — one session query and one
        customer query for the whole batch, never one per case. Soft-deleted
        customers still resolve to their historical name/VIP (no deleted_at filter).
        """
        session_ids = {c.session_id for c in cases if c.customer_id is None}
        session_customer: dict = {}
        if session_ids:
            rows = self._s.execute(
                select(CallSession.id, CallSession.customer_id).where(CallSession.id.in_(session_ids))
            ).all()
            session_customer = {str(session_id): customer_id for session_id, customer_id in rows}

        customer_ids = {
            case.customer_id if case.customer_id is not None else session_customer.get(str(case.session_id))
            for case in cases
        }
        customer_ids.discard(None)

        customers: dict = {}
        if customer_ids:
            rows = self._s.execute(
                select(Customer.id, Customer.first_name, Customer.last_name, Customer.vip_flag)
                .where(Customer.id.in_(customer_ids))
            ).all()
            customers = {str(cid): (first, last, vip) for cid, first, last, vip in rows}

        out = []
        for case in cases:
            cid = case.customer_id
            if cid is None:
                cid = session_customer.get(str(case.session_id))
            name_vip = customers.get(str(cid)) if cid is not None else None
            out.append({
                "id": str(case.id), "session_id": str(case.session_id), "trigger": case.trigger,
                "target": case.target, "resolution": case.resolution, "dossier": case.dossier,
                "created_at": case.created_at.isoformat() if case.created_at else None,
                # Batch 5 — customer identity projection. customer_id: the case's own id wins,
                # then the session's, then null (a dangling id is kept, name/VIP stay null).
                # customer_name / customer_vip: null when the identity is unresolved.
                "customer_id": str(cid) if cid is not None else None,
                "customer_name": f"{name_vip[0]} {name_vip[1]}".strip() if name_vip else None,
                "customer_vip": bool(name_vip[2]) if name_vip else None,
            })
        return out

    def escalations(self, status: str = "open") -> list[dict]:
        stmt = select(EscalationCase)
        if status == "open":
            stmt = stmt.where(EscalationCase.resolution.is_(None))
        rows = self._s.scalars(
            stmt.order_by(EscalationCase.created_at.desc()).limit(_ESCALATION_LIMIT)
        ).all()
        return self._project_escalation_cases(list(rows))

    _ESCALATION_RESOLUTIONS = ("transferred", "queued", "callback_scheduled", "resolved")

    def close_escalation(self, escalation_id: str, resolution: str) -> dict:
        """Set the outcome on an open handoff. Idempotent per row: a case that already carries a
        resolution is returned unchanged rather than overwritten.
        """
        if resolution not in self._ESCALATION_RESOLUTIONS:
            raise ValueError(f"unsupported resolution: {resolution}")

        case = self._s.get(EscalationCase, to_uuid(escalation_id))
        if case is None:
            return {}
        if case.resolution is None:
            case.resolution = resolution
            self._s.flush()

        return self._project_escalation_cases([case])[0]

    def verdicts(self, session_id: str) -> list[dict]:
        sid = to_uuid(session_id)
        if sid is None:
            return []
        rows = self._s.scalars(
            select(PolicyVerdict).where(PolicyVerdict.session_id == sid).order_by(PolicyVerdict.created_at)
        ).all()
        return [
            {"id": str(v.id), "action": v.requested_action, "verdict": v.verdict,
             "rule_id": v.rule_id, "justification": v.justification}
            for v in rows
        ]

    def actions(self, status: str = "failed") -> list[dict]:
        rows = self._s.scalars(
            select(ActionLedger).where(ActionLedger.status == status).order_by(ActionLedger.created_at.desc())
        ).all()
        return [
            {"id": str(a.id), "action_type": a.action_type, "status": a.status,
             "idempotency_key": a.idempotency_key, "reference": a.adapter_reference}
            for a in rows
        ]

    def decision_ledger(
        self,
        *,
        verdict: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Verdicts newest-first, each with the actions it authorized. Read-only.

        C8: exposes the verdict -> actions parent/child chain (execution.action_ledger's
        policy_verdict_id FK is mandatory, so every action belongs to exactly one verdict).
        One verdict query + one batched action query — no N+1. Additive; verdicts() and
        actions() keep their exact projections for their existing consumers.
        """
        stmt = select(PolicyVerdict).order_by(PolicyVerdict.created_at.desc()).limit(limit)

        if verdict:
            stmt = stmt.where(PolicyVerdict.verdict == verdict)

        sid = to_uuid(session_id) if session_id else None
        if session_id and sid is None:
            # Mirrors verdicts(): an explicitly-supplied malformed id is a miss, not a 500.
            return []
        if sid is not None:
            stmt = stmt.where(PolicyVerdict.session_id == sid)

        rows = self._s.scalars(stmt).all()

        actions_by_verdict: dict = {}
        if rows:
            ids = [v.id for v in rows]
            action_rows = self._s.scalars(
                select(ActionLedger).where(ActionLedger.policy_verdict_id.in_(ids))
            ).all()
            for a in action_rows:
                actions_by_verdict.setdefault(str(a.policy_verdict_id), []).append({
                    "id": str(a.id),
                    "action_type": a.action_type,
                    "target_domain": a.target_domain,
                    "status": a.status,
                    "attempt_count": a.attempt_count,
                    "idempotency_key": a.idempotency_key,
                    "reference": a.adapter_reference,
                    "error_message": a.error_message,
                    "parameters": a.parameters,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                })

        return [
            {
                "id": str(v.id),
                "session_id": str(v.session_id),
                "customer_id": str(v.customer_id) if v.customer_id else None,
                "action": v.requested_action,
                "direction": v.direction,
                "verdict": v.verdict,
                "rule_id": v.rule_id,
                "justification": v.justification,
                "inputs_snapshot": v.inputs_snapshot,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "actions": actions_by_verdict.get(str(v.id), []),
            }
            for v in rows
        ]

    def business_rules(self) -> list[dict]:
        rows = self._s.scalars(select(BusinessRule).order_by(BusinessRule.domain, BusinessRule.rule_id)).all()
        return [
            {"rule_id": r.rule_id, "domain": r.domain, "version": r.version, "active": r.active,
             "description": r.description, "definition": r.definition_json}
            for r in rows
        ]

    # ---------------------------------------------------------------- reference catalog writes
    #
    # These catalogs ARE runtime inputs, unlike the policy registry: the agent reads products,
    # recharges and geo areas while a caller is on the line. So an edit here changes what the
    # agent can offer on the very next call, which is the point.
    #
    # Two protections follow from that:
    #   - a product or recharge in use is DEACTIVATED rather than deleted, so historical rows that
    #     reference it keep resolving;
    #   - a geo area with children or outages cannot be deleted at all, because oss.outages.area_code
    #     is a foreign key here and orphaning it would let an outage name a zone that no longer
    #     exists — the exact failure the geo_areas table was introduced to make impossible.

    def create_product(self, product_code: str, name: str, plan_type: str) -> dict:
        code = (product_code or "").strip().upper()
        if not code:
            raise ValueError("product_code is required")
        if plan_type not in {"PREPAID", "POSTPAID"}:
            raise ValueError("plan_type must be PREPAID or POSTPAID")
        if self._s.scalar(select(Product).where(Product.product_code == code)):
            raise ValueError(f"{code} already exists")

        row = Product(product_code=code, name=(name or code).strip()[:120],
                      plan_type=plan_type, active=True)
        self._s.add(row)
        self._s.flush()
        return {"product_code": row.product_code, "name": row.name,
                "plan_type": row.plan_type, "active": row.active}

    def update_product(self, product_code: str, name: str | None = None,
                       plan_type: str | None = None, active: bool | None = None) -> dict | None:
        row = self._s.scalar(select(Product).where(Product.product_code == product_code))
        if row is None:
            return None
        if plan_type is not None:
            if plan_type not in {"PREPAID", "POSTPAID"}:
                raise ValueError("plan_type must be PREPAID or POSTPAID")
            row.plan_type = plan_type
        if name is not None and name.strip():
            row.name = name.strip()[:120]
        if active is not None:
            row.active = active
        self._s.flush()
        return {"product_code": row.product_code, "name": row.name,
                "plan_type": row.plan_type, "active": row.active}

    def delete_product(self, product_code: str) -> bool:
        """Delete an UNUSED plan. A plan a subscription points at is deactivated instead."""
        from persistence.models.crm import Subscription

        row = self._s.scalar(select(Product).where(Product.product_code == product_code))
        if row is None:
            return False
        in_use = self._s.scalar(
            select(func.count()).select_from(Subscription)
            .where(Subscription.plan_code == product_code)
        ) or 0
        if int(in_use) > 0:
            raise ValueError(
                f"{product_code} is used by {int(in_use)} subscription(s); deactivate it instead "
                "so existing subscriptions keep resolving"
            )
        self._s.delete(row)
        return True

    def create_recharge(self, code: str, amount: float, bonus_amount: float = 0.0) -> dict:
        clean = (code or "").strip().upper()
        if not clean:
            raise ValueError("code is required")
        if amount is None or float(amount) <= 0:
            raise ValueError("amount must be greater than zero")
        if float(bonus_amount or 0) < 0:
            raise ValueError("bonus_amount cannot be negative")
        if self._s.scalar(select(RechargeCatalog).where(RechargeCatalog.code == clean)):
            raise ValueError(f"{clean} already exists")

        row = RechargeCatalog(code=clean, amount=amount, bonus_amount=bonus_amount or 0)
        self._s.add(row)
        self._s.flush()
        return {"code": row.code, "amount": float(row.amount),
                "bonus_amount": float(row.bonus_amount)}

    def update_recharge(self, code: str, amount: float | None = None,
                        bonus_amount: float | None = None) -> dict | None:
        row = self._s.scalar(select(RechargeCatalog).where(RechargeCatalog.code == code))
        if row is None:
            return None
        if amount is not None:
            if float(amount) <= 0:
                raise ValueError("amount must be greater than zero")
            row.amount = amount
        if bonus_amount is not None:
            if float(bonus_amount) < 0:
                raise ValueError("bonus_amount cannot be negative")
            row.bonus_amount = bonus_amount
        self._s.flush()
        return {"code": row.code, "amount": float(row.amount),
                "bonus_amount": float(row.bonus_amount)}

    def delete_recharge(self, code: str) -> bool:
        row = self._s.scalar(select(RechargeCatalog).where(RechargeCatalog.code == code))
        if row is None:
            return False
        self._s.delete(row)
        return True

    def create_geo_area(self, area_code: str, name_fr: str, area_type: str,
                        parent_code: str | None = None, name_ar: str | None = None,
                        name_en: str | None = None) -> dict:
        code = (area_code or "").strip().upper()
        if not code:
            raise ValueError("area_code is required")
        if area_type not in {"governorate", "delegation", "locality"}:
            raise ValueError("area_type must be governorate, delegation or locality")
        if self._s.scalar(select(GeoArea).where(GeoArea.area_code == code)):
            raise ValueError(f"{code} already exists")
        parent = (parent_code or "").strip().upper() or None
        if parent and not self._s.scalar(select(GeoArea).where(GeoArea.area_code == parent)):
            raise ValueError(f"parent {parent} does not exist")

        row = GeoArea(area_code=code, name_fr=(name_fr or code).strip()[:120],
                      name_ar=(name_ar or None), name_en=(name_en or None),
                      area_type=area_type, parent_code=parent, active=True)
        self._s.add(row)
        self._s.flush()
        return {"area_code": row.area_code, "name": row.name_fr, "area_type": row.area_type,
                "parent_code": row.parent_code, "active": row.active}

    def update_geo_area(self, area_code: str, name_fr: str | None = None,
                        active: bool | None = None, name_ar: str | None = None,
                        name_en: str | None = None) -> dict | None:
        row = self._s.scalar(select(GeoArea).where(GeoArea.area_code == area_code))
        if row is None:
            return None
        if name_fr is not None and name_fr.strip():
            row.name_fr = name_fr.strip()[:120]
        if name_ar is not None:
            row.name_ar = name_ar.strip() or None
        if name_en is not None:
            row.name_en = name_en.strip() or None
        if active is not None:
            row.active = active
        self._s.flush()
        return {"area_code": row.area_code, "name": row.name_fr, "area_type": row.area_type,
                "parent_code": row.parent_code, "active": row.active}

    def delete_geo_area(self, area_code: str) -> bool:
        """Refused while anything still points at the area — see the note above."""
        from persistence.models.oss import Outage

        row = self._s.scalar(select(GeoArea).where(GeoArea.area_code == area_code))
        if row is None:
            return False

        children = self._s.scalar(
            select(func.count()).select_from(GeoArea).where(GeoArea.parent_code == area_code)
        ) or 0
        if int(children) > 0:
            raise ValueError(f"{area_code} has {int(children)} child area(s); remove them first")

        outages = self._s.scalar(
            select(func.count()).select_from(Outage).where(Outage.area_code == area_code)
        ) or 0
        if int(outages) > 0:
            raise ValueError(
                f"{area_code} is referenced by {int(outages)} outage record(s); "
                "deactivate the area instead"
            )

        self._s.delete(row)
        return True

    # ---------------------------------------------------------------- outages
    #
    # This is the surface the agent actually speaks from. get_network_status() resolves a caller's
    # spoken place to an area_code, walks the geo hierarchy, and reads the ACTIVE outages here —
    # so an outage opened in the console is audible on the next call, and a description written
    # here is the sentence the caller hears.

    #: Mirrors the ck_outages_cause CHECK constraint exactly. Kept here so an unknown cause is
    #: refused with a readable message instead of surfacing a raw IntegrityError to the console.
    #: Note the spelling: the column allows "fiber_cut", not "fibre_cut".
    OUTAGE_CAUSES = (
        "fiber_cut",
        "power_failure",
        "equipment_failure",
        "planned_maintenance",
        "congestion",
        "weather",
        "third_party_damage",
    )

    def list_outages(self, active_only: bool = False, limit: int = 200) -> list[dict]:
        from persistence.models.oss import Outage

        stmt = select(Outage).order_by(Outage.start_time.desc())
        if active_only:
            stmt = stmt.where(Outage.resolved.is_(False))
        rows = self._s.scalars(stmt.limit(max(1, min(limit, 500)))).all()

        # The area's human name, resolved in one query rather than per row.
        codes = {r.area_code for r in rows if r.area_code}
        names = {}
        if codes:
            names = {
                g.area_code: g.name_fr
                for g in self._s.scalars(select(GeoArea).where(GeoArea.area_code.in_(codes))).all()
            }

        return [
            {
                "id": str(r.id),
                "area_code": r.area_code,
                "area_name": names.get(r.area_code) if r.area_code else None,
                "area": r.area,
                "region": r.region,
                "severity": r.severity,
                "cause": r.cause,
                "affected_services": r.affected_services,
                "resolved": r.resolved,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "description_fr": r.description_fr,
                "description_ar": r.description_ar,
                "description_en": r.description_en,
            }
            for r in rows
        ]

    def create_outage(self, *, area_code: str, severity: str, cause: str | None,
                      affected_services: str | None, description_fr: str | None,
                      description_ar: str | None, description_en: str | None,
                      start_time=None, end_time=None) -> dict:
        from persistence.models.oss import Outage

        code = (area_code or "").strip().upper()
        area = self._s.scalar(select(GeoArea).where(GeoArea.area_code == code))
        if area is None:
            # The FK would reject this anyway; failing here gives the console a usable message.
            raise ValueError(f"unknown area_code {code}")
        if severity not in {"minor", "major", "critical"}:
            raise ValueError("severity must be minor, major or critical")
        if cause and cause not in self.OUTAGE_CAUSES:
            raise ValueError(f"cause must be one of {', '.join(self.OUTAGE_CAUSES)}")
        if not (description_fr or "").strip():
            # The agent speaks FR by default and falls back to it for every other language, so an
            # outage without a French description is one the agent can detect but not explain.
            raise ValueError("description_fr is required — it is what the agent says to callers")

        row = Outage(
            area_code=code,
            area=area.name_fr,
            region=area.parent_code or area.name_fr,
            severity=severity,
            cause=(cause or None),
            affected_services=(affected_services or None),
            description_fr=description_fr.strip(),
            description_ar=(description_ar or None),
            description_en=(description_en or None),
            resolved=False,
        )
        if start_time is not None:
            row.start_time = start_time
        if end_time is not None:
            row.end_time = end_time
        self._s.add(row)
        self._s.flush()
        return {"id": str(row.id), "area_code": row.area_code, "severity": row.severity,
                "resolved": row.resolved}

    def update_outage(self, outage_id: str, *, severity: str | None = None,
                      resolved: bool | None = None, end_time=None,
                      description_fr: str | None = None, description_ar: str | None = None,
                      description_en: str | None = None) -> dict | None:
        from persistence.models.oss import Outage

        oid = to_uuid(outage_id)
        row = self._s.get(Outage, oid) if oid else None
        if row is None:
            return None

        if severity is not None:
            if severity not in {"minor", "major", "critical"}:
                raise ValueError("severity must be minor, major or critical")
            row.severity = severity
        if description_fr is not None and description_fr.strip():
            row.description_fr = description_fr.strip()
        if description_ar is not None:
            row.description_ar = description_ar.strip() or None
        if description_en is not None:
            row.description_en = description_en.strip() or None
        if end_time is not None:
            row.end_time = end_time
        if resolved is not None:
            row.resolved = resolved
            # Closing an outage without an end time leaves "when did it stop?" unanswerable.
            if resolved and row.end_time is None:
                from datetime import UTC, datetime as _dt

                row.end_time = _dt.now(UTC)

        self._s.flush()
        return {"id": str(row.id), "area_code": row.area_code, "severity": row.severity,
                "resolved": row.resolved,
                "end_time": row.end_time.isoformat() if row.end_time else None}

    # ---------------------------------------------------------------- policy registry writes
    #
    # SAFETY, stated once and enforced below.
    #
    # `reference.business_rules` is a GOVERNANCE RECORD, not a runtime input. Its only readers are
    # this admin view and the seed script - policy-service, decision-service and agent-worker never
    # query it (they read POLICY_* env). So editing a row here cannot change what the agent does.
    #
    # Two invariants keep that true, and both are refusals rather than silent coercions:
    #   1. Numeric thresholds are NEVER writable. They live in POLICY_* and are overlaid at read
    #      time (see policy_view.overlay); accepting one here would let the registry claim a limit
    #      the engine is not applying - exactly the drift the overlay exists to prevent.
    #   2. A GOVERNED rule cannot be deactivated or deleted. Its row documents a guardrail that IS
    #      being enforced; removing or disabling the documentation while the env var still applies
    #      would make the registry lie about live behaviour.

    def _governed_rule_ids(self) -> set[str]:
        """Rule ids whose thresholds come from POLICY_* env (imported lazily to avoid a cycle)."""
        from business_api.policy_view import GOVERNED_BY

        return set(GOVERNED_BY)

    def get_business_rule(self, rule_id: str) -> dict | None:
        row = self._s.scalar(select(BusinessRule).where(BusinessRule.rule_id == rule_id))
        if row is None:
            return None
        return {"rule_id": row.rule_id, "domain": row.domain, "version": row.version,
                "active": row.active, "description": row.description,
                "definition": row.definition_json}

    def create_business_rule(self, rule_id: str, domain: str, description: str | None) -> dict:
        """Add a CATALOG rule (governance record only). Raises ValueError on a conflict."""
        rule_id = rule_id.strip()
        if not rule_id:
            raise ValueError("rule_id is required")
        if rule_id in self._governed_rule_ids():
            # Creating a row under a governed id would fabricate a guardrail: the overlay would
            # then attach live enforced numbers to a rule nobody actually configured.
            raise ValueError(f"{rule_id} is a governed rule id and cannot be created here")
        if self._s.scalar(select(BusinessRule).where(BusinessRule.rule_id == rule_id)):
            raise ValueError(f"{rule_id} already exists")

        row = BusinessRule(
            rule_id=rule_id,
            domain=(domain or "general").strip()[:40],
            description=(description or None),
            definition_json={},
            version=1,
            active=True,
        )
        self._s.add(row)
        self._s.flush()
        return {"rule_id": row.rule_id, "domain": row.domain, "version": row.version,
                "active": row.active, "description": row.description, "definition": {}}

    def update_business_rule(
        self, rule_id: str, description: str | None = None, active: bool | None = None
    ) -> dict | None:
        """Patch the writable governance fields. Returns None when the rule does not exist.

        `version` is bumped on every accepted change: this is a versioned registry, and a
        description edited without a version change is indistinguishable from the original.
        """
        row = self._s.scalar(select(BusinessRule).where(BusinessRule.rule_id == rule_id))
        if row is None:
            return None

        governed = rule_id in self._governed_rule_ids()
        if governed and active is False:
            raise ValueError(
                f"{rule_id} is enforced from POLICY_* env and cannot be deactivated here; "
                "change the environment variable and restart policy-service instead"
            )

        changed = False
        if description is not None and description != row.description:
            row.description = description or None
            changed = True
        if active is not None and active != row.active:
            row.active = active
            changed = True

        if changed:
            row.version = (row.version or 1) + 1
        self._s.flush()

        return {"rule_id": row.rule_id, "domain": row.domain, "version": row.version,
                "active": row.active, "description": row.description,
                "definition": row.definition_json, "changed": changed}

    def delete_business_rule(self, rule_id: str) -> bool:
        """Remove a CATALOG rule. Governed rules are refused; returns False when absent."""
        if rule_id in self._governed_rule_ids():
            raise ValueError(
                f"{rule_id} documents an enforced guardrail and cannot be deleted"
            )
        row = self._s.scalar(select(BusinessRule).where(BusinessRule.rule_id == rule_id))
        if row is None:
            return False
        self._s.delete(row)
        return True

    def reference_catalog(self, catalog: str, search: str = "", limit: int = 200) -> list[dict]:
        """Read one admin-managed reference catalog (spec section 13.1). Read-only."""
        limit = max(1, min(limit, 500))
        term = f"%{search.strip().lower()}%" if search and search.strip() else None

        if catalog == "errors":
            stmt = select(ErrorCatalog).order_by(ErrorCatalog.domain, ErrorCatalog.code)
            if term is not None:
                stmt = stmt.where(
                    func.lower(ErrorCatalog.code).like(term)
                    | func.lower(func.coalesce(ErrorCatalog.message_fr, "")).like(term)
                )
            return [
                {"code": r.code, "domain": r.domain, "message_fr": r.message_fr,
                 "message_ar": r.message_ar, "message_en": r.message_en}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "products":
            stmt = select(Product).order_by(Product.plan_type, Product.product_code)
            if term is not None:
                stmt = stmt.where(
                    func.lower(Product.product_code).like(term) | func.lower(Product.name).like(term)
                )
            return [
                {"product_code": r.product_code, "name": r.name,
                 "plan_type": r.plan_type, "active": r.active}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "recharges":
            stmt = select(RechargeCatalog).order_by(RechargeCatalog.amount)
            if term is not None:
                stmt = stmt.where(func.lower(RechargeCatalog.code).like(term))
            return [
                {"code": r.code, "amount": float(r.amount),
                 "bonus_amount": float(r.bonus_amount)}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        if catalog == "areas":
            stmt = select(GeoArea).order_by(GeoArea.area_type, GeoArea.name_fr)
            if term is not None:
                stmt = stmt.where(
                    func.lower(GeoArea.area_code).like(term)
                    | func.lower(GeoArea.name_fr).like(term)
                    | func.lower(func.coalesce(GeoArea.name_ar, "")).like(term)
                )
            return [
                {"area_code": r.area_code, "name_fr": r.name_fr, "name_ar": r.name_ar,
                 "name_en": r.name_en, "area_type": r.area_type,
                 "parent_code": r.parent_code, "active": r.active}
                for r in self._s.scalars(stmt.limit(limit)).all()
            ]

        return []

    def kpis(self) -> Kpis:
        total = self._s.scalar(select(func.count()).select_from(CallSession)) or 0
        resolved = self._s.scalar(
            select(func.count()).select_from(CallSession).where(CallSession.final_disposition == "resolved")
        ) or 0
        escalated = self._s.scalar(
            select(func.count()).select_from(CallSession).where(CallSession.final_disposition == "escalated")
        ) or 0
        avg_frustration = self._s.scalar(select(func.coalesce(func.avg(CallSession.max_frustration_score), 0)))
        return compute_kpis(total, resolved, escalated, avg_frustration)

    def system_overview(self) -> dict:
        from persistence.models.audit import AuditLedgerEntry

        total_calls = self._s.scalar(select(func.count()).select_from(CallSession)) or 0
        total_turns = self._s.scalar(select(func.count()).select_from(Turn)) or 0
        total_verdicts = self._s.scalar(select(func.count()).select_from(PolicyVerdict)) or 0
        total_actions = self._s.scalar(select(func.count()).select_from(ActionLedger)) or 0
        total_audit = self._s.scalar(select(func.count()).select_from(AuditLedgerEntry)) or 0
        total_customers = self._s.scalar(select(func.count()).select_from(Customer)) or 0
        total_escalations = self._s.scalar(select(func.count()).select_from(EscalationCase)) or 0

        services = [
            {"name": "context-service", "port": 8101, "domain": "Customer 360 & Auth"},
            {"name": "knowledge-service", "port": 8102, "domain": "Semantic RAG & Documents"},
            {"name": "decision-service", "port": 8103, "domain": "Risk Scoring & Candidate Ranking"},
            {"name": "policy-service", "port": 8104, "domain": "Phase 0 Deterministic Gate"},
            {"name": "execution-service", "port": 8105, "domain": "Idempotent Action Ledger"},
            {"name": "notification-service", "port": 8106, "domain": "Multi-channel Messaging"},
            {"name": "token-service", "port": 8107, "domain": "LiveKit JWT Auth"},
            {"name": "business-api", "port": 8108, "domain": "Supervisor & Admin API"},
            {"name": "ai-knowledge-rag", "port": 8201, "domain": "Qdrant Vector Search MCP"},
            {"name": "ticketing-glpi", "port": 8202, "domain": "GLPI Ticketing MCP"},
            {"name": "messaging-gateway", "port": 8203, "domain": "SMS/Email Gateway MCP"},
        ]
        return {
            "metrics": {
                "total_calls": total_calls,
                "total_turns": total_turns,
                "total_verdicts": total_verdicts,
                "total_actions": total_actions,
                "total_audit_entries": total_audit,
                "total_customers": total_customers,
                "total_escalations": total_escalations,
            },
            "services": services,
        }

    def telemetry_timeline(self) -> dict:
        sessions = self._s.scalars(select(CallSession).order_by(CallSession.created_at.desc()).limit(50)).all()
        verdicts = self._s.scalars(select(PolicyVerdict).order_by(PolicyVerdict.created_at.desc()).limit(100)).all()

        timeline_points = []
        for s in reversed(sessions):
            timeline_points.append({
                "timestamp": s.created_at.strftime("%H:%M:%S") if s.created_at else "00:00:00",
                "duration": s.duration_seconds or 0,
                "frustration": float(s.max_frustration_score or 0.0),
                "disposition": s.final_disposition or "unknown",
            })

        authorized = sum(1 for v in verdicts if v.verdict.upper() == "AUTHORIZED")
        refused = sum(1 for v in verdicts if v.verdict.upper() == "REFUSED")
        escalated = sum(1 for v in verdicts if v.verdict.upper() == "ESCALATE")

        return {
            "timeline": timeline_points,
            "verdict_distribution": {
                "authorized": authorized,
                "refused": refused,
                "escalated": escalated,
            },
        }

    def analytics_trend(self, days: int = 7) -> dict:
        """Windowed KPI bundle (current vs previous equal window) + daily volume buckets.

        Reuses compute_kpis unchanged; only the time filter is new. Buckets are cut in the
        business timezone so a "day" on the chart matches a day on the floor.
        """
        from datetime import UTC, datetime, timedelta

        tz_name = os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis")
        now = datetime.now(UTC)
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)

        def _bundle(start: datetime, end: datetime) -> Kpis:
            window = (CallSession.created_at >= start, CallSession.created_at < end)
            total = self._s.scalar(
                select(func.count()).select_from(CallSession).where(*window)) or 0
            resolved = self._s.scalar(
                select(func.count()).select_from(CallSession).where(
                    *window, CallSession.final_disposition == "resolved")) or 0
            escalated = self._s.scalar(
                select(func.count()).select_from(CallSession).where(
                    *window, CallSession.final_disposition == "escalated")) or 0
            avg = self._s.scalar(
                select(func.coalesce(func.avg(CallSession.max_frustration_score), 0)).where(*window))
            return compute_kpis(total, resolved, escalated, avg)

        local_day = func.date(func.timezone(tz_name, CallSession.created_at))
        rows = self._s.execute(
            select(local_day.label("day"), func.count().label("n"))
            .where(CallSession.created_at >= previous_start)
            .group_by(local_day)
        ).all()
        buckets = {str(r.day): int(r.n) for r in rows}

        daily = []
        for offset in range(days):
            cur = (current_start + timedelta(days=offset)).date().isoformat()
            prev = (previous_start + timedelta(days=offset)).date().isoformat()
            daily.append({
                "day": cur,
                "current": buckets.get(cur, 0),
                "previous": buckets.get(prev, 0),
            })

        return {
            "days": days,
            "timezone": tz_name,
            "current": _bundle(current_start, now).__dict__,
            "previous": _bundle(previous_start, current_start).__dict__,
            "daily": daily,
        }

    def agent_activity(self, days: int = 30) -> dict:
        """Truthful per-persona call attribution and provider token telemetry.

        Five fixed set-based aggregations (no N+1): distinct (persona, call)
        pairs from turns, per-persona call/duration rolls, per-persona token
        rolls, and a global unique-call series. Windows are UTC half-open
        ranges [midnight of oldest day, now). Durations are non-exclusive
        attributed call durations: every persona observed in a call receives
        that call's full persisted duration.
        """
        days = max(1, min(int(days), 365))
        now = datetime.now(UTC)
        from_day = now.date() - timedelta(days=days - 1)
        from_ts = datetime.combine(from_day, time.min, tzinfo=UTC)
        to_ts = now
        day_keys = [
            (from_day + timedelta(days=offset)).isoformat()
            for offset in range(days)
        ]

        persona_calls = (
            select(
                Turn.active_agent.label("persona"),
                Turn.session_id.label("session_id"),
            )
            .join(CallSession, CallSession.id == Turn.session_id)
            .where(
                CallSession.start_time >= from_ts,
                CallSession.start_time < to_ts,
                Turn.active_agent.isnot(None),
                Turn.active_agent != "",
            )
            .distinct()
            .cte("persona_calls")
        )
        call_day = func.date(func.timezone("UTC", CallSession.start_time))
        token_day = func.date(func.timezone("UTC", AgentUsageEvent.occurred_at))

        call_rows = self._s.execute(
            select(
                persona_calls.c.persona,
                func.count().label("attributed_calls"),
                func.count(CallSession.duration_seconds).label("completed_calls"),
                func.coalesce(
                    func.sum(CallSession.duration_seconds),
                    0,
                ).label("attributed_duration"),
                func.avg(CallSession.duration_seconds).label("average_duration"),
                func.max(CallSession.start_time).label("last_call_at"),
            )
            .join(CallSession, CallSession.id == persona_calls.c.session_id)
            .group_by(persona_calls.c.persona)
        ).all()

        call_daily_rows = self._s.execute(
            select(
                persona_calls.c.persona,
                call_day.label("day"),
                func.count().label("attributed_calls"),
                func.coalesce(
                    func.sum(CallSession.duration_seconds),
                    0,
                ).label("attributed_duration"),
            )
            .join(CallSession, CallSession.id == persona_calls.c.session_id)
            .group_by(persona_calls.c.persona, call_day)
        ).all()

        token_rows = self._s.execute(
            select(
                AgentUsageEvent.agent.label("persona"),
                func.count().label("token_event_count"),
                func.sum(AgentUsageEvent.input_tokens).label("input_tokens"),
                func.sum(AgentUsageEvent.output_tokens).label("output_tokens"),
                func.max(AgentUsageEvent.occurred_at).label("last_token_at"),
            )
            .where(
                AgentUsageEvent.occurred_at >= from_ts,
                AgentUsageEvent.occurred_at < to_ts,
            )
            .group_by(AgentUsageEvent.agent)
        ).all()

        token_daily_rows = self._s.execute(
            select(
                AgentUsageEvent.agent.label("persona"),
                token_day.label("day"),
                func.count().label("token_event_count"),
                func.sum(AgentUsageEvent.input_tokens).label("input_tokens"),
                func.sum(AgentUsageEvent.output_tokens).label("output_tokens"),
            )
            .where(
                AgentUsageEvent.occurred_at >= from_ts,
                AgentUsageEvent.occurred_at < to_ts,
            )
            .group_by(AgentUsageEvent.agent, token_day)
        ).all()

        global_call_rows = self._s.execute(
            select(
                call_day.label("day"),
                func.count(CallSession.id).label("unique_calls"),
            )
            .where(
                CallSession.start_time >= from_ts,
                CallSession.start_time < to_ts,
            )
            .group_by(call_day)
        ).all()

        call_stats = {row.persona: row for row in call_rows}
        call_daily = {(row.persona, row.day.isoformat()): row for row in call_daily_rows}
        token_stats = {row.persona: row for row in token_rows}
        token_daily = {(row.persona, row.day.isoformat()): row for row in token_daily_rows}
        global_daily = {row.day.isoformat(): row.unique_calls for row in global_call_rows}

        personas = sorted(set(call_stats) | set(token_stats))

        persona_rows = []
        for persona in personas:
            call = call_stats.get(persona)
            token = token_stats.get(persona)
            last_observed = max(
                (
                    value
                    for value in (
                        call.last_call_at if call else None,
                        token.last_token_at if token else None,
                    )
                    if value is not None
                ),
                default=None,
            )
            daily = []
            for day in day_keys:
                call_point = call_daily.get((persona, day))
                token_point = token_daily.get((persona, day))
                daily.append(
                    {
                        "day": day,
                        "attributed_calls": call_point.attributed_calls if call_point else 0,
                        "attributed_call_duration_seconds": (
                            call_point.attributed_duration if call_point else 0
                        ),
                        "provider_input_tokens": (
                            token_point.input_tokens if token_point else None
                        ),
                        "provider_output_tokens": (
                            token_point.output_tokens if token_point else None
                        ),
                    }
                )
            persona_rows.append(
                {
                    "persona": persona,
                    "attributed_calls": int(call.attributed_calls) if call else 0,
                    "completed_calls": int(call.completed_calls) if call else 0,
                    "attributed_call_duration_seconds": int(call.attributed_duration) if call else 0,
                    "average_completed_call_duration_seconds": (
                        float(call.average_duration) if call and call.average_duration is not None else None
                    ),
                    "last_observed_at": last_observed.isoformat() if last_observed is not None else None,
                    "provider_input_tokens": int(token.input_tokens) if token else None,
                    "provider_output_tokens": int(token.output_tokens) if token else None,
                    "token_event_count": int(token.token_event_count) if token else 0,
                    "daily": daily,
                }
            )

        persona_rows.sort(
            key=lambda row: (row["attributed_call_duration_seconds"], row["attributed_calls"]),
            reverse=True,
        )

        token_totals = [row["provider_input_tokens"] for row in persona_rows if row["provider_input_tokens"] is not None]
        has_token_events = any(token is not None for token in token_totals)

        return {
            "window": {
                "days": days,
                "timezone": "UTC",
                "from": from_ts.isoformat(),
                "to": to_ts.isoformat(),
            },
            "definitions": {
                "agent_kind": "persona_class",
                "duration_kind": "non_exclusive_attributed_call_duration",
                "token_source": "provider_reported",
                "token_history": "forward_only_no_backfill",
            },
            "totals": {
                "global_unique_calls": sum(global_daily.values()),
                "persona_call_attributions": sum(row["attributed_calls"] for row in persona_rows),
                "attributed_call_duration_seconds": sum(
                    row["attributed_call_duration_seconds"] for row in persona_rows
                ),
                "provider_input_tokens": (
                    sum(int(row["provider_input_tokens"]) for row in persona_rows if row["provider_input_tokens"] is not None)
                    if has_token_events else None
                ),
                "provider_output_tokens": (
                    sum(int(row["provider_output_tokens"]) for row in persona_rows if row["provider_output_tokens"] is not None)
                    if has_token_events else None
                ),
            },
            "personas": persona_rows,
        }

    def audit_entries(self, limit: int = 50, before_seq: int | None = None,
                      event_type: str | None = None) -> dict:
        """Most recent audit ledger entries, newest first. Read-only; keyset paging on seq."""
        from persistence.models.audit import AuditLedgerEntry

        stmt = select(AuditLedgerEntry).order_by(AuditLedgerEntry.seq.desc()).limit(limit + 1)
        if before_seq is not None:
            stmt = stmt.where(AuditLedgerEntry.seq < before_seq)
        if event_type:
            stmt = stmt.where(AuditLedgerEntry.event_type == event_type)

        rows = list(self._s.scalars(stmt))
        has_more = len(rows) > limit
        rows = rows[:limit]

        return {
            "entries": [
                {
                    "seq": r.seq,
                    "event_type": r.event_type,
                    "entity_reference": r.entity_reference,
                    "session_id": str(r.session_id) if r.session_id else None,
                    "entry_hash": r.entry_hash,
                    "previous_hash": r.previous_hash,
                    "created_at": r.created_at.isoformat(),
                    "payload": r.payload,
                }
                for r in rows
            ],
            "has_more": has_more,
            "next_before_seq": rows[-1].seq if rows and has_more else None,
        }