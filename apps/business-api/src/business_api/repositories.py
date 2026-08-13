"""Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."""
from __future__ import annotations

import os

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from business_api.kpis import Kpis, compute_kpis
from persistence.models.billing import Account, Invoice, Notification, Payment, PaymentPlan
from persistence.models.conversation import CallSession, EscalationCase, SentimentSample, Turn
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
            "vip": customer.vip_flag,
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

    def escalations(self, status: str = "open") -> list[dict]:
        rows = self._s.scalars(select(EscalationCase).order_by(EscalationCase.created_at.desc())).all()
        out = []
        for case in rows:
            is_open = case.resolution is None
            if status == "open" and not is_open:
                continue
            out.append({
                "id": str(case.id), "session_id": str(case.session_id), "trigger": case.trigger,
                "target": case.target, "resolution": case.resolution, "dossier": case.dossier,
                # Batch 1 / C13: expose created_at (the query already orders by it) and
                # customer_id (present on the model, one join from Customer 360). Additive keys —
                # consumed by the admin dashboard only; supervisor-dashboard ignores them.
                # APPROVED in the C13 audit follow-up (2026-08-04): JSON-additive and nullable-safe;
                # Cookbook 13 §8.1/§8.3 originally deferred both pending sign-off.
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "customer_id": str(case.customer_id) if case.customer_id else None,
            })
        return out

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
        """Per-persona activity aggregated from conversation.turns.active_agent.

        Read-only. Windows on CallSession.start_time (confirmed present),
        joining turns to their session rather than relying on a Turn timestamp.
        """
        from datetime import UTC, datetime, timedelta

        window_days = max(1, min(int(days or 30), 365))
        since = datetime.now(UTC) - timedelta(days=window_days)

        rows = self._s.execute(
            select(
                Turn.active_agent.label("agent"),
                func.count(Turn.id).label("turn_count"),
                func.count(func.distinct(Turn.session_id)).label("session_count"),
                func.max(CallSession.start_time).label("last_seen"),
            )
            .join(CallSession, CallSession.id == Turn.session_id)
            .where(CallSession.start_time >= since)
            # P0-3/P1-1 - count CALLER turns only. Before P0-3 every row in
            # conversation.turns was a caller row, so this predicate was a no-op and
            # its absence was invisible. The moment agent turns persist, omitting it
            # would roughly double the number under a column labelled "Caller turns".
            .where(Turn.speaker == "caller")
            .where(Turn.active_agent.isnot(None))
            .where(Turn.active_agent != "")
            .group_by(Turn.active_agent)
            .order_by(func.count(Turn.id).desc())
        ).all()

        agents = [
            {
                "agent": row.agent,
                "turns": int(row.turn_count or 0),
                "sessions": int(row.session_count or 0),
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        ]
        return {
            "window_days": window_days,
            "total_turns": sum(a["turns"] for a in agents),
            "total_sessions": sum(a["sessions"] for a in agents),
            "agents": agents,
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