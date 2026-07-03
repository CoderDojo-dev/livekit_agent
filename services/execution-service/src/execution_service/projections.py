"""Domain write projections (spec sections 5-7): the durable effect of an AUTHORIZED action.

When the (mock) adapter dispatch succeeds, the action's effect is projected into the owning
domain schema - a captured payment, a deferral plan, a recharge, a SIM case - carrying the same
idempotency_key as execution.action_ledger and the policy_verdict_id that authorized it. The
projection runs in a SAVEPOINT inside the execute transaction, so a projection problem can never
undo the action ledger or the audit chain. Defensive: missing data logs and skips.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.billing import Account, Invoice, Payment, PaymentPlan
from persistence.models.ocs import Recharge
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest
from persistence.models.sim import BlockUnblockCase
from persistence.util import to_uuid

logger = logging.getLogger(__name__)

# ---- pure mapping (offline-testable) ----
_PROJECTION = {
    "EXECUTE_PAYMENT": "payment", "PAYMENT_DEFERRAL": "payment_plan",
    "TOP_UP": "recharge", "UNBLOCK_SIM": "sim_case", "REACTIVATE_SIM": "sim_case",
    "CHANGE_PLAN": "provisioning", "ACTIVATE_ROAMING": "provisioning",
}
_SIM_ACTION = {"UNBLOCK_SIM": "UNBLOCK", "REACTIVATE_SIM": "REACTIVATE"}


def projection_kind(action_type: str) -> str | None:
    """Which domain table an action projects into (None if it has no projection)."""
    return _PROJECTION.get(action_type)


def sim_case_action(action_type: str) -> str | None:
    """Map a SIM action_type to the block_unblock_cases.action value."""
    return _SIM_ACTION.get(action_type)


def installment_amount(total, count) -> float:
    """Even per-installment amount (>=1 installment), rounded to millimes."""
    count = max(1, int(count or 1))
    return round(float(total or 0) / count, 3)


# ---- DB projection ----
def project_domain_effect(session: Session, req, ledger_row) -> None:
    """Write the domain row for ``req`` (dispatch already succeeded). Caller wraps this in a savepoint."""
    kind = projection_kind(req.action_type)
    if kind == "payment":
        _payment(session, req, ledger_row)
    elif kind == "payment_plan":
        _payment_plan(session, req, ledger_row)
    elif kind == "recharge":
        _recharge(session, req, ledger_row)
    elif kind == "sim_case":
        _sim_case(session, req, ledger_row)
    elif kind == "provisioning":
        _provisioning(session, req, ledger_row)


def _account_for(session: Session, customer_id):
    cid = to_uuid(customer_id)
    return session.scalar(select(Account).where(Account.customer_id == cid)) if cid else None


def _payment(session: Session, req, ledger_row) -> None:
    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("payment projection skipped: no billing account for %s", req.customer_id)
        return
    invoice = None
    inv_num = req.payload.get("invoice_id") or req.payload.get("invoice_number")
    if inv_num:
        invoice = session.scalar(select(Invoice).where(Invoice.invoice_number == str(inv_num)))
    session.add(Payment(
        account_id=account.id,
        invoice_id=invoice.id if invoice else None,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        method=req.payload.get("method", "card"),
        gateway_reference=ledger_row.adapter_reference,
        idempotency_key=req.idempotency_key,
        status="succeeded",
        paid_at=datetime.now(UTC),
    ))


def _payment_plan(session: Session, req, ledger_row) -> None:
    account = _account_for(session, req.customer_id)
    if account is None:
        logger.warning("plan projection skipped: no billing account for %s", req.customer_id)
        return
    total = req.payload.get("amount") or req.payload.get("unpaid_amount") or 0
    count = req.payload.get("installment_count") or 1
    session.add(PaymentPlan(
        account_id=account.id,
        customer_id=to_uuid(req.customer_id),
        total_amount=total,
        installment_count=count,
        installment_amount=installment_amount(total, count),
        status="active",
        policy_verdict_id=to_uuid(req.policy_verdict_id),
    ))


def _recharge(session: Session, req, ledger_row) -> None:
    sid = to_uuid(req.subscription_id)
    if sid is None:
        logger.warning("recharge projection skipped: no subscription on request")
        return
    session.add(Recharge(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        amount=req.payload.get("amount") or 0,
        channel="agent",
        idempotency_key=req.idempotency_key,
        transaction_reference=ledger_row.adapter_reference,
        status="completed",
    ))


def _sim_case(session: Session, req, ledger_row) -> None:
    action = sim_case_action(req.action_type)
    sid = to_uuid(req.subscription_id)
    if action is None or sid is None:
        logger.warning("sim projection skipped: action=%s subscription=%s", action, req.subscription_id)
        return
    session.add(BlockUnblockCase(
        subscription_id=sid,
        action=action,
        status="completed",
        identity_verified=True,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        idempotency_key=req.idempotency_key,
    ))


def _provisioning(session: Session, req, ledger_row) -> None:
    from datetime import datetime

    sid = to_uuid(req.subscription_id)
    session.add(ProvisioningRequest(
        subscription_id=sid,
        customer_id=to_uuid(req.customer_id),
        action_type=req.action_type,
        status="completed",
        idempotency_key=req.idempotency_key,
        policy_verdict_id=to_uuid(req.policy_verdict_id),
        parameters=req.payload,
        completed_at=datetime.now(UTC),
    ))
    if req.action_type == "CHANGE_PLAN" and sid is not None:
        session.add(PlanChangeHistory(
            subscription_id=sid,
            from_plan=req.payload.get("from_plan"),
            to_plan=str(req.payload.get("plan_code") or "unknown"),
            changed_by="agent",
        ))
