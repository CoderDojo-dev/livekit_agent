"""business-api entrypoint (spec section 17): read-or-audited supervisor/admin endpoints.

RBAC per the section 17 matrix (conseiller / superviseur / administrateur). No endpoint mutates
the audit ledger; the integrity job only verifies it.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from business_api import advisors as advisor_repo
from business_api import availability as availability_repo
from business_api import callbacks as callback_repo
from business_api import policy_view, portal_auth
from business_api.infrastructure.auth import rate_limit
from business_api.infrastructure.auth.principal import (
    Principal,
    bearer_token,
    current_client,
    current_principal,
)
from business_api.jobs.integrity import run_integrity
from business_api.jobs.retention import run_retention
from business_api.repositories import SupervisionRepository
from business_api.security import require_role
from persistence import get_session

app = FastAPI(title="business-api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5174").split(","),
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

DbSession = Annotated[Session, Depends(get_session)]
ConseillerRole = Annotated[str, Depends(require_role("conseiller"))]
SuperviseurRole = Annotated[str, Depends(require_role("superviseur"))]
AdministrateurRole = Annotated[str, Depends(require_role("administrateur"))]
CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
ClientPrincipal = Annotated[Principal, Depends(current_client)]


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


# ---------------- Authentication (P0-1). One identity layer, two front ends. ----------------
class LoginPayload(BaseModel):
    """Credentials for either portal. The role comes from the account, never from the client."""

    email: str
    password: str


class SignupPayload(BaseModel):
    """A subscriber CLAIMING their existing account. It never creates telecom data."""

    msisdn: str
    cin_last4: str
    email: str
    password: str


class PasswordChangePayload(BaseModel):
    """Rotate your own password. Closes every other session."""

    current_password: str
    new_password: str


_AUTH_STATUS = {
    "invalid_credentials": 401,
    "signup_failed": 401,
    "weak_password": 400,
    "locked": 429,
    "rate_limited": 429,
}


def _client_ip(request: Request) -> str:
    """Best-effort caller address for throttling. Never used for authorisation."""
    return request.client.host if request.client else "unknown"


def _auth_http(error: portal_auth.AuthError) -> HTTPException:
    return HTTPException(
        status_code=_AUTH_STATUS.get(error.code, 401), detail=error.message
    )


@app.post("/api/v1/auth/login")
def auth_login(payload: LoginPayload, request: Request, session: DbSession) -> dict:
    """Exchange credentials for an opaque bearer token. Ungated by design."""
    bucket = f"login:{_client_ip(request)}"
    if not rate_limit.check(bucket):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    try:
        account = portal_auth.authenticate(session, payload.email, payload.password)
    except portal_auth.AuthError as error:
        raise _auth_http(error) from None

    rate_limit.reset(bucket)
    token, expires_at = portal_auth.open_session(
        session,
        account,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "email": account.email,
        "role": account.role,
        "kind": account.kind,
        "customer_id": str(account.customer_id) if account.customer_id else None,
    }


@app.post("/api/v1/auth/signup")
def auth_signup(payload: SignupPayload, request: Request, session: DbSession) -> dict:
    """Create a CLIENT login for an existing subscriber. Staff accounts are never self-served."""
    bucket = f"signup:{_client_ip(request)}"
    if not rate_limit.check(bucket, limit=10):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    try:
        account = portal_auth.signup_client(
            session,
            msisdn=payload.msisdn,
            cin_last4=payload.cin_last4,
            email=payload.email,
            password=payload.password,
        )
    except portal_auth.AuthError as error:
        raise _auth_http(error) from None

    token, expires_at = portal_auth.open_session(
        session,
        account,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "token": token,
        "expires_at": expires_at.isoformat(),
        "email": account.email,
        "role": account.role,
        "kind": account.kind,
        "customer_id": str(account.customer_id),
    }


@app.post("/api/v1/auth/logout")
def auth_logout(request: Request, session: DbSession, principal: CurrentPrincipal) -> dict:
    """Revoke the presented session. Idempotent."""
    token = bearer_token(request.headers.get("authorization"))
    if token:
        portal_auth.revoke_session(session, token)
    return {"signed_out": True}


@app.get("/api/v1/auth/me")
def auth_me(principal: CurrentPrincipal) -> dict:
    """Who the presented credential belongs to. The front ends use this to validate a session."""
    return {
        "subject": principal.subject,
        "kind": principal.kind,
        "role": principal.role,
        "customer_id": str(principal.customer_id) if principal.customer_id else None,
    }


@app.post("/api/v1/auth/password")
def auth_change_password(
    payload: PasswordChangePayload, session: DbSession, principal: CurrentPrincipal
) -> dict:
    """Change your own password. Machine principals have no password to change."""
    if principal.account_id is None:
        raise HTTPException(status_code=403, detail="requires a user account")
    try:
        revoked = portal_auth.change_password(
            session, principal.account_id, payload.current_password, payload.new_password
        )
    except portal_auth.AuthError as error:
        raise _auth_http(error) from None
    return {"changed": True, "sessions_revoked": revoked}


@app.post("/api/v1/auth/sessions/revoke-all")
def auth_revoke_all(session: DbSession, principal: CurrentPrincipal) -> dict:
    """Sign out of all devices. Backs the affordance already rendered on the portal Security page."""
    if principal.account_id is None:
        raise HTTPException(status_code=403, detail="requires a user account")
    return {"sessions_revoked": portal_auth.revoke_all(session, principal.account_id)}


# ---------------- Client portal reads. Scoped by the TOKEN, never by the URL. ----------------
@app.get("/api/v1/me/profile")
def me_profile(session: DbSession, principal: ClientPrincipal) -> dict:
    """The signed-in customer's own 360.

    customer_id comes from the authenticated principal, so there is no identifier in the request
    for a caller to tamper with: client A cannot address customer B's data at all.
    """
    data = SupervisionRepository(session).customer_360(str(principal.customer_id))
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/customers")
def list_customers(
    session: DbSession,
    role: ConseillerRole,
    search: str = "",
    status: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict:
    """Paginated CRM customer registry (admin dashboard lookup)."""
    return SupervisionRepository(session).customer_list(search, status, limit, offset)


@app.get("/api/v1/customers/{customer_id}/360")
def customer_360(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Full Customer-360 (profile + subscriptions + open invoices + tickets)."""
    data = SupervisionRepository(session).customer_360(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/customers/{customer_id}/ledger")
def customer_ledger(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Payments, deferral plans and consent captures for one customer (read-only)."""
    data = SupervisionRepository(session).customer_ledger(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/customers/{customer_id}/service-actions")
def customer_service_actions(customer_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Live balances, plan history and service-action projections for one customer (read-only)."""
    data = SupervisionRepository(session).customer_service_actions(customer_id)
    if data is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return data


@app.get("/api/v1/tickets")
def ticket_index(session: DbSession, role: SuperviseurRole, limit: int = 50, offset: int = 0,
                 status: str | None = None, category: str | None = None,
                 priority: str | None = None, customer_id: str | None = None,
                 search: str | None = None) -> dict:
    """Supervision list over the local GLPI ticket mirror.

    GLPI stays the source of truth. This never writes: ticket mutations must go through the
    ticketing-glpi MCP server so GLPI is updated first and the mirror stays consistent.
    """
    return SupervisionRepository(session).ticket_list(
        limit=limit, offset=offset, status=status, category=category,
        priority=priority, customer_id=customer_id, search=search,
    )


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


@app.get("/api/v1/sessions")
def session_index(session: DbSession, role: SuperviseurRole, limit: int = 50, offset: int = 0,
                  disposition: str | None = None, customer_id: str | None = None,
                  search: str | None = None) -> dict:
    """Paginated index of call sessions (supervision list view).

    The detail endpoint below answers "what happened on this call"; this one answers
    "which calls exist", which is otherwise undiscoverable from outside the database.
    """
    return SupervisionRepository(session).session_list(
        limit=limit, offset=offset, disposition=disposition,
        customer_id=customer_id, search=search,
    )


@app.get("/api/v1/sessions/{session_id}")
def session_detail(session_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Masked transcript + sentiment timeline + disposition for a call session."""
    data = SupervisionRepository(session).session_detail(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.get("/api/v1/escalations")
def escalations(session: DbSession, role: SuperviseurRole, status: str = "open") -> dict:
    """Escalation queue with dossiers."""
    return {"escalations": SupervisionRepository(session).escalations(status)}


@app.get("/api/v1/policy/verdicts")
def verdicts(session_id: str, session: DbSession, role: SuperviseurRole) -> dict:
    """All policy verdicts for a session (audit review)."""
    return {"verdicts": SupervisionRepository(session).verdicts(session_id)}


@app.get("/api/v1/decisions")
def decisions(
    session: DbSession,
    role: SuperviseurRole,
    verdict: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
) -> dict:
    """Policy decisions newest-first with the actions they authorized (supervision review)."""
    return {
        "decisions": SupervisionRepository(session).decision_ledger(
            verdict=verdict, session_id=session_id, limit=limit
        )
    }


@app.get("/api/v1/actions")
def actions(session: DbSession, role: SuperviseurRole, status: str = "failed") -> dict:
    """Failed / retrying actions from the action ledger."""
    return {"actions": SupervisionRepository(session).actions(status)}


@app.get("/api/v1/kpis")
def kpis(session: DbSession, role: SuperviseurRole) -> dict:
    """Containment / escalation KPIs over the persisted conversation record."""
    return SupervisionRepository(session).kpis().__dict__


@app.get("/api/v1/system/overview")
def system_overview(session: DbSession, role: SuperviseurRole) -> dict:
    """Real-time system overview: database counts + service status matrix."""
    return SupervisionRepository(session).system_overview()


@app.get("/api/v1/telemetry/timeline")
def telemetry_timeline(session: DbSession, role: SuperviseurRole) -> dict:
    """Time-series metrics and verdict distributions derived from persisted records."""
    return SupervisionRepository(session).telemetry_timeline()


@app.get("/api/v1/agents/activity")
def agent_activity(session: DbSession, role: SuperviseurRole, days: int = 30) -> dict:
    """Per-persona activity aggregated from conversation turns."""
    return SupervisionRepository(session).agent_activity(days)


@app.get("/api/v1/analytics/trend")
def analytics_trend(session: DbSession, role: SuperviseurRole, days: int = 7) -> dict:
    """Windowed KPIs versus the preceding equal window, plus daily volume buckets."""
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90")
    return SupervisionRepository(session).analytics_trend(days)


@app.get("/api/v1/audit/verify")
def audit_verify(
    session: DbSession,
    role: AdministrateurRole,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> dict:
    """Run the hash-chain integrity check (whole chain; range is a later refinement)."""
    ledger = PgAuditLedger(session)
    return {"intact": ledger.verify(), "entries": ledger.count()}


@app.get("/api/v1/audit/entries")
def audit_entries(session: DbSession, role: AdministrateurRole, limit: int = 50,
                  before_seq: int | None = None, event_type: str | None = None) -> dict:
    """Browse the append-only audit ledger, newest first (read-only)."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return SupervisionRepository(session).audit_entries(limit, before_seq, event_type)


@app.get("/api/v1/reference/business-rules")
def business_rules(session: DbSession, role: AdministrateurRole) -> dict:
    """List the versioned Policy rule registry with the LIVE enforced thresholds.

    The DB row supplies governance metadata; the numeric thresholds are overlaid from the same
    POLICY_* env the policy engine enforces, so the registry can never drift from what is applied.
    """
    rows = SupervisionRepository(session).business_rules()
    return {"rules": policy_view.overlay(rows)}


@app.get("/api/v1/reference/catalogs/{catalog}")
def reference_catalog(
    catalog: str,
    db: DbSession,
    _role: AdministrateurRole,
    search: str = "",
    limit: int = 200,
) -> list[dict]:
    """Read one admin-managed reference catalog (spec section 13.1). Read-only."""
    if catalog not in {"errors", "products", "recharges", "areas"}:
        raise HTTPException(status_code=404, detail="unknown catalog")
    return SupervisionRepository(db).reference_catalog(catalog, search, limit)


@app.get("/api/v1/jobs/integrity")
def integrity(session: DbSession, role: AdministrateurRole) -> dict:
    """Cross-domain referential integrity + audit-chain verification (spec section 20.4)."""
    report = run_integrity(session)
    return {
        "ok": report.ok, "orphans": report.orphans,
        "audit_chain_intact": report.audit_chain_intact, "audit_entries": report.audit_entries,
    }


@app.post("/api/v1/jobs/retention")
def retention(
    session: DbSession,
    role: AdministrateurRole,
    retention_days: int = 90,
    dry_run: bool = True,
) -> dict:
    """Run the audited retention/purge job (dry_run=True by default) - spec section 8.3."""
    if retention_days < 30:
        raise HTTPException(status_code=422, detail="retention_days must be >= 30")
    return run_retention(session, retention_days=retention_days, dry_run=dry_run).__dict__


# ---------------- Advisor working hours (admin dashboard + agent negotiation) ----------------
class ShiftWindow(BaseModel):
    """One working window, in business-local time."""

    weekday: int          # 0 = Monday ... 6 = Sunday
    start: str            # "08:00"
    end: str              # "16:00"
    is_active: bool = True


class ShiftGrid(BaseModel):
    """The complete weekly grid for one advisor. Sent whole, replaced whole."""

    windows: list[ShiftWindow]


class TimeOffPayload(BaseModel):
    """A dated absence (ISO-8601 instants)."""

    starts_at: str
    ends_at: str
    reason: str | None = None


# Coverage must be declared BEFORE {advisor_id} routes so FastAPI doesn't route "coverage" as an id.
@app.get("/api/v1/advisors/coverage")
def advisor_coverage(session: DbSession, role: SuperviseurRole, days: int = 7) -> dict:
    """Hour-by-hour coverage, including the hours nobody covers (supervision view)."""
    return availability_repo.coverage_report(session, days)


@app.get("/api/v1/advisors/{advisor_id}/schedule")
def advisor_schedule(advisor_id: str, session: DbSession, role: SuperviseurRole) -> dict:
    """One advisor's weekly grid plus upcoming absences (dashboard detail panel)."""
    return availability_repo.advisor_week(session, advisor_id)


@app.put("/api/v1/advisors/{advisor_id}/schedule")
def replace_advisor_schedule(advisor_id: str, grid: ShiftGrid, session: DbSession,
                             role: AdministrateurRole) -> dict:
    """Replace an advisor's whole weekly grid. Overlapping windows are rejected."""
    try:
        shifts = availability_repo.replace_shifts(
            session, advisor_id, [w.model_dump() for w in grid.windows]
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="advisor not found")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    session.commit()
    return {"advisor_id": advisor_id, "shifts": shifts}


@app.get("/api/v1/advisors/{advisor_id}/time-off")
def advisor_time_off(advisor_id: str, session: DbSession, role: SuperviseurRole,
                     upcoming_only: bool = True) -> dict:
    """An advisor's absences."""
    return {"time_off": availability_repo.list_time_off(session, advisor_id, upcoming_only)}


@app.post("/api/v1/advisors/{advisor_id}/time-off", status_code=201)
def create_advisor_time_off(advisor_id: str, payload: TimeOffPayload, session: DbSession,
                            role: AdministrateurRole) -> dict:
    """Declare an absence; it removes the advisor from every slot it covers, immediately."""
    try:
        created = availability_repo.create_time_off(
            session, advisor_id, payload.starts_at, payload.ends_at, payload.reason
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="advisor not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    session.commit()
    return created


@app.delete("/api/v1/advisors/time-off/{time_off_id}")
def delete_advisor_time_off(time_off_id: str, session: DbSession,
                            role: AdministrateurRole) -> dict:
    """Cancel an absence; the weekly grid applies again from that instant."""
    if not availability_repo.delete_time_off(session, time_off_id):
        raise HTTPException(status_code=404, detail="time off not found")
    session.commit()
    return {"deleted": True, "time_off_id": time_off_id}


# ---------------- Advisor registry (admin dashboard + agent routing) ----------------
class AdvisorPayload(BaseModel):
    """Advisor create/update body. Skills are tags matched against the escalating persona."""

    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    sip_uri: str | None = None
    skills: list[str] | None = None
    language: str | None = None
    status: str | None = None
    max_concurrent_calls: int | None = None
    is_on_call: bool | None = None
    is_active: bool | None = None


@app.get("/api/v1/advisors")
def list_advisors(session: DbSession, role: SuperviseurRole, include_inactive: bool = False) -> dict:
    """List advisors (admin dashboard)."""
    return {"advisors": advisor_repo.list_advisors(session, include_inactive)}


@app.post("/api/v1/advisors", status_code=201)
def create_advisor(payload: AdvisorPayload, session: DbSession, role: AdministrateurRole) -> dict:
    """Register a new advisor."""
    if not payload.full_name:
        raise HTTPException(status_code=400, detail="full_name is required")
    try:
        result = advisor_repo.create_advisor(session, payload.model_dump(exclude_none=True))
        session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/v1/advisors/{advisor_id}")
def update_advisor(advisor_id: str, payload: AdvisorPayload, session: DbSession,
                   role: AdministrateurRole) -> dict:
    """Update an advisor (availability, skills, contact details)."""
    try:
        updated = advisor_repo.update_advisor(session, advisor_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return updated


@app.delete("/api/v1/advisors/{advisor_id}")
def delete_advisor(advisor_id: str, session: DbSession, role: AdministrateurRole) -> dict:
    """Remove an advisor from the registry."""
    if not advisor_repo.delete_advisor(session, advisor_id):
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return {"deleted": True, "advisor_id": advisor_id}


@app.post("/api/v1/advisors/claim")
def claim_advisor(session: DbSession, role: ConseillerRole, skill_tag: str = "general") -> dict:
    """Atomically reserve an available advisor for ``skill_tag`` (used by the voice agent).

    Returns {"advisor": null} when nobody is free - the caller then offers a callback. It never
    invents a destination.
    """
    claimed = advisor_repo.claim_advisor(session, skill_tag)
    session.commit()
    return {"advisor": claimed}


@app.post("/api/v1/advisors/{advisor_id}/release")
def release_advisor(advisor_id: str, session: DbSession, role: ConseillerRole) -> dict:
    """Release a claimed advisor (call ended, or the transfer failed)."""
    if not advisor_repo.release_advisor(session, advisor_id):
        raise HTTPException(status_code=404, detail="advisor not found")
    session.commit()
    return {"released": True, "advisor_id": advisor_id}


@app.get("/api/v1/advisors/on-call")
def on_call_advisors(session: DbSession, role: ConseillerRole) -> dict:
    """Advisors who receive the dossier when a callback is scheduled."""
    return {"advisors": advisor_repo.on_call_advisors(session)}


# ---------------- Callback queue (the promise made when no advisor was free) ----------------
class CallbackReservation(BaseModel):
    """A slot the caller agreed to, plus who it is for."""

    slot_start: str
    customer_id: str | None = None
    subscription_id: str | None = None
    session_id: str | None = None
    preferred_window: str | None = None
    reason: str | None = None


class CallbackOutcome(BaseModel):
    """Result of an attempted callback."""

    note: str = ""
    reached: bool = True      # False -> the caller did not answer; return it to the queue
    advisor_id: str | None = None


@app.get("/api/v1/callbacks/slots")
def callback_slots(session: DbSession, role: ConseillerRole, days: int = 2, limit: int = 6,
                   day: str | None = None, skill_tag: str | None = None,
                   language: str | None = None) -> dict:
    """Bookable slots, soonest first. ``day`` (YYYY-MM-DD) answers "what about Thursday?"."""
    return {"slots": callback_repo.free_slots(session, days, limit, day, skill_tag, language)}


@app.get("/api/v1/callbacks/check")
def callback_check(requested: str, session: DbSession, role: ConseillerRole,
                   alternatives: int = 3, skill_tag: str | None = None,
                   language: str | None = None) -> dict:
    """Is this exact time bookable? Returns a reason and the nearest real alternatives.

    This is what makes the negotiation honest: the agent proposes only times this endpoint
    returned, and declines with a reason it did not invent.
    """
    return callback_repo.check_slot(session, requested, alternatives, skill_tag, language)


@app.post("/api/v1/callbacks/reserve", status_code=201)
def reserve_callback(payload: CallbackReservation, session: DbSession,
                     role: ConseillerRole) -> dict:
    """Book one slot for a caller. 409 when it was taken between the offer and the answer."""
    booked = callback_repo.reserve(session, **payload.model_dump())
    if booked is None:
        raise HTTPException(status_code=409, detail="slot no longer available")
    session.commit()
    return booked


@app.get("/api/v1/callbacks")
def list_callbacks(session: DbSession, role: ConseillerRole, status: str = "pending",
                   overdue_only: bool = False, limit: int = 100) -> dict:
    """The callback queue, soonest and highest priority first."""
    return {"callbacks": callback_repo.list_callbacks(session, status, overdue_only, limit)}


@app.get("/api/v1/callbacks/stats")
def callback_stats(session: DbSession, role: SuperviseurRole) -> dict:
    """Queue health: pending, overdue, completed."""
    return callback_repo.queue_stats(session)


@app.post("/api/v1/callbacks/claim")
def claim_callback(session: DbSession, role: ConseillerRole, advisor_id: str | None = None) -> dict:
    """Atomically take the next due callback. {"callback": null} when the queue is empty."""
    claimed = callback_repo.claim_next(session, advisor_id)
    session.commit()
    return {"callback": claimed}


@app.post("/api/v1/callbacks/{callback_id}/complete")
def complete_callback(callback_id: str, outcome: CallbackOutcome, session: DbSession,
                      role: ConseillerRole) -> dict:
    """Close a callback with its outcome, or return it to the queue if the caller did not answer."""
    updated = callback_repo.complete_callback(session, callback_id, outcome.note, outcome.reached)
    if updated is None:
        raise HTTPException(status_code=404, detail="callback not found")
    session.commit()
    return updated


@app.post("/api/v1/callbacks/{callback_id}/cancel")
def cancel_callback(callback_id: str, outcome: CallbackOutcome, session: DbSession,
                    role: SuperviseurRole) -> dict:
    """Cancel a callback that is no longer needed."""
    updated = callback_repo.cancel_callback(session, callback_id, outcome.note)
    if updated is None:
        raise HTTPException(status_code=404, detail="callback not found")
    session.commit()
    return updated


def run() -> None:
    """Console-script entrypoint: `business-api` (see [project.scripts]). Serves on :8108."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8108)
