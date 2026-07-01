"""Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from business_api.kpis import Kpis, compute_kpis
from persistence.models.billing import Invoice
from persistence.models.conversation import CallSession, EscalationCase, SentimentSample, Turn
from persistence.models.crm import Customer, Subscription
from persistence.models.execution import ActionLedger
from persistence.models.policy import PolicyVerdict
from persistence.models.reference import BusinessRule
from persistence.models.ticketing import Ticket
from persistence.util import to_uuid


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
                {"invoice": i.invoice_number, "amount": float(i.total_amount), "status": i.status}
                for i in invoices if i.status != "paid"
            ],
            "tickets": [{"glpi_id": t.glpi_ticket_id, "status": t.status, "subject": t.subject} for t in tickets],
        }

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
            })
        return out

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

    def business_rules(self) -> list[dict]:
        rows = self._s.scalars(select(BusinessRule).order_by(BusinessRule.domain, BusinessRule.rule_id)).all()
        return [
            {"rule_id": r.rule_id, "domain": r.domain, "version": r.version, "active": r.active,
             "description": r.description, "definition": r.definition_json}
            for r in rows
        ]

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