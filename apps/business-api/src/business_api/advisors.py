"""Advisor registry operations: CRUD for the admin dashboard, and the atomic claim for routing.

The claim is the delicate part. Two escalations happening at the same instant must never be
handed the same advisor, so the candidate row is locked with FOR UPDATE SKIP LOCKED (the same
pattern the knowledge outbox worker uses): each concurrent claimer locks a different row instead
of queueing on the first one, and capacity is re-checked inside the lock before the counter moves.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.routing import Advisor

logger = logging.getLogger(__name__)


def _skills(advisor: Advisor) -> set[str]:
    return {s.strip().lower() for s in (advisor.skills or "").split(",") if s.strip()}


def to_dict(advisor: Advisor) -> dict:
    """Serialize an advisor for the API (no secrets are stored on this row)."""
    return {
        "id": str(advisor.id),
        "full_name": advisor.full_name,
        "email": advisor.email,
        "phone_e164": advisor.phone_e164,
        "sip_uri": advisor.sip_uri,
        "skills": [s for s in (advisor.skills or "").split(",") if s],
        "language": advisor.language,
        "status": advisor.status,
        "max_concurrent_calls": advisor.max_concurrent_calls,
        "active_calls": advisor.active_calls,
        "is_on_call": advisor.is_on_call,
        "is_active": advisor.is_active,
    }


def list_advisors(session: Session, include_inactive: bool = False) -> list[dict]:
    stmt = select(Advisor).order_by(Advisor.full_name.asc())
    if not include_inactive:
        stmt = stmt.where(Advisor.is_active.is_(True))
    return [to_dict(a) for a in session.scalars(stmt)]


def get_advisor(session: Session, advisor_id: str) -> Advisor | None:
    from persistence.util import to_uuid

    aid = to_uuid(advisor_id)
    return session.get(Advisor, aid) if aid else None


def create_advisor(session: Session, data: dict) -> dict:
    """Create an advisor. Requires at least one reachable destination (phone or SIP URI)."""
    if not data.get("phone_e164") and not data.get("sip_uri"):
        raise ValueError("an advisor needs a phone_e164 or a sip_uri to be reachable")
    advisor = Advisor(
        full_name=data["full_name"],
        email=data.get("email"),
        phone_e164=data.get("phone_e164"),
        sip_uri=data.get("sip_uri"),
        skills=",".join(data.get("skills") or ["general"]),
        language=data.get("language") or "fr",
        status=data.get("status") or "offline",
        max_concurrent_calls=int(data.get("max_concurrent_calls") or 1),
        is_on_call=bool(data.get("is_on_call", False)),
        is_active=bool(data.get("is_active", True)),
    )
    session.add(advisor)
    session.flush()
    return to_dict(advisor)


def update_advisor(session: Session, advisor_id: str, data: dict) -> dict | None:
    advisor = get_advisor(session, advisor_id)
    if advisor is None:
        return None
    for field in ("full_name", "email", "phone_e164", "sip_uri", "language", "status"):
        if field in data and data[field] is not None:
            setattr(advisor, field, data[field])
    if data.get("skills") is not None:
        advisor.skills = ",".join(data["skills"]) or "general"
    if data.get("max_concurrent_calls") is not None:
        advisor.max_concurrent_calls = int(data["max_concurrent_calls"])
    for flag in ("is_on_call", "is_active"):
        if data.get(flag) is not None:
            setattr(advisor, flag, bool(data[flag]))
    if not advisor.phone_e164 and not advisor.sip_uri:
        raise ValueError("an advisor needs a phone_e164 or a sip_uri to be reachable")
    return to_dict(advisor)


def delete_advisor(session: Session, advisor_id: str) -> bool:
    advisor = get_advisor(session, advisor_id)
    if advisor is None:
        return False
    session.delete(advisor)
    return True


def claim_advisor(session: Session, skill_tag: str) -> dict | None:
    """Atomically reserve an available advisor for ``skill_tag``; None when nobody is free.

    Locks candidates with SKIP LOCKED so concurrent escalations pick different advisors, then
    re-checks capacity inside the lock before incrementing active_calls.
    """
    wanted = (skill_tag or "general").strip().lower()
    stmt = (
        select(Advisor)
        .where(
            Advisor.is_active.is_(True),
            Advisor.status == "available",
            Advisor.active_calls < Advisor.max_concurrent_calls,
        )
        .order_by(Advisor.active_calls.asc(), Advisor.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    for advisor in session.scalars(stmt):
        skills = _skills(advisor)
        if wanted not in skills and "general" not in skills:
            continue
        if advisor.active_calls >= advisor.max_concurrent_calls:
            continue
        advisor.active_calls += 1
        if advisor.active_calls >= advisor.max_concurrent_calls:
            advisor.status = "busy"
        logger.info("advisor %s claimed for %s", advisor.full_name, wanted)
        return to_dict(advisor)
    return None


def release_advisor(session: Session, advisor_id: str) -> bool:
    """Free a claimed advisor (call ended or transfer failed) and restore availability."""
    advisor = get_advisor(session, advisor_id)
    if advisor is None:
        return False
    if advisor.active_calls > 0:
        advisor.active_calls -= 1
    if advisor.status == "busy" and advisor.active_calls < advisor.max_concurrent_calls:
        advisor.status = "available"
    return True


def on_call_advisors(session: Session) -> list[dict]:
    """Advisors who should receive the dossier when no one could take the call live."""
    stmt = select(Advisor).where(Advisor.is_active.is_(True), Advisor.is_on_call.is_(True))
    return [to_dict(a) for a in session.scalars(stmt)]