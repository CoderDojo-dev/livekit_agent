"""Read-side queries for the supervision endpoints (spec section 17). Read-only; never mutates audit."""
from __future__ import annotations

import os

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
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "customer_id": str(case.customer_id) if case.customer_id else None,
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
            {"name": "context-service", "port": 8101, "domain": "Customer 360 & Auth", "status": "online"},
            {"name": "knowledge-service", "port": 8102, "domain": "Semantic RAG & Documents", "status": "online"},
            {"name": "decision-service", "port": 8103, "domain": "Risk Scoring & Candidate Ranking", "status": "online"},
            {"name": "policy-service", "port": 8104, "domain": "Phase 0 Deterministic Gate", "status": "online"},
            {"name": "execution-service", "port": 8105, "domain": "Idempotent Action Ledger", "status": "online"},
            {"name": "notification-service", "port": 8106, "domain": "Multi-channel Messaging", "status": "online"},
            {"name": "token-service", "port": 8107, "domain": "LiveKit JWT Auth", "status": "online"},
            {"name": "business-api", "port": 8108, "domain": "Supervisor & Admin API", "status": "online"},
            {"name": "ai-knowledge-rag", "port": 8201, "domain": "Qdrant Vector Search MCP", "status": "online"},
            {"name": "ticketing-glpi", "port": 8202, "domain": "GLPI Ticketing MCP", "status": "online"},
            {"name": "messaging-gateway", "port": 8203, "domain": "SMS/Email Gateway MCP", "status": "online"},
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