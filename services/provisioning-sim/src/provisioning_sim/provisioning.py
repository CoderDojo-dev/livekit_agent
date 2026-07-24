"""The real provisioning ledger behind the SIM/plan/roaming simulator.

This replaces an in-memory dict that reported success for operations that never happened: it
created a SIM record for any key it was given, kept no idempotency, and lost everything on
restart - so the agent could tell a caller "your SIM is unblocked" while the real line stayed
blocked. Every operation now mutates the real domain tables and is protected by the database's own
uniqueness on idempotency_key, like the OCS/billing ledger:

  unblock_sim     -> sim.block_unblock_cases (UNBLOCK)     + subscriptions.status  -> ACTIVE
  reactivate_sim  -> sim.block_unblock_cases (REACTIVATE)  + subscriptions.status  -> ACTIVE
  replace_sim     -> provisioning.sim_orders + provisioning.provisioning_requests
  change_plan     -> provisioning.plan_change_history      + subscriptions.plan_code
  set_roaming     -> provisioning.provisioning_requests    + subscriptions.roaming_enabled

State transitions are validated, not forced: unblocking a line that is not BLOCKED, or reactivating
a TERMINATED one, is refused with a reason the agent can say out loud. Refusing is the honest
answer - claiming success on an impossible change is what the previous implementation did.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models.crm import Subscription
from persistence.models.provisioning import PlanChangeHistory, ProvisioningRequest, SimOrder
from persistence.models.sim import BlockUnblockCase
from persistence.util import to_uuid

logger = logging.getLogger(__name__)

ACTIVE, SUSPENDED, BLOCKED, TERMINATED = "ACTIVE", "SUSPENDED", "BLOCKED", "TERMINATED"


class ProvisioningError(RuntimeError):
    """A provisioning operation could not complete. Surfaced honestly, never faked."""


def _subscription(session: Session, customer_id: str) -> Subscription:
    cid = to_uuid(customer_id)
    if cid is None:
        raise ProvisioningError(f"{customer_id!r} is not a valid customer id")
    subscription = session.scalar(
        select(Subscription).where(Subscription.customer_id == cid)
        .order_by(Subscription.created_at.asc())
    )
    if subscription is None:
        raise ProvisioningError(f"customer {customer_id} has no subscription")
    return subscription


def _reference(prefix: str, key: str) -> str:
    """Deterministic reference for an idempotency key, so a replay returns the same value."""
    return f"{prefix}-{key[:10].upper()}"


def _existing_case(session: Session, key: str) -> BlockUnblockCase | None:
    return session.scalar(select(BlockUnblockCase).where(BlockUnblockCase.idempotency_key == key))


def _existing_request(session: Session, key: str) -> ProvisioningRequest | None:
    return session.scalar(
        select(ProvisioningRequest).where(ProvisioningRequest.idempotency_key == key)
    )


# ---------------- SIM lifecycle ----------------
def _sim_case(session: Session, customer_id: str, action: str, key: str,
              allowed_from: set[str]) -> str:
    if _existing_case(session, key) is not None:
        return _reference("SIM", key)  # idempotent replay: no second provisioning

    subscription = _subscription(session, customer_id)
    if subscription.status not in allowed_from:
        raise ProvisioningError(
            f"cannot {action.lower()}: the line is {subscription.status}, "
            f"expected one of {sorted(allowed_from)}"
        )

    session.add(BlockUnblockCase(
        subscription_id=subscription.id, action=action, status="completed",
        identity_verified=True,  # execution is only reached after the identity-gated verdict
        idempotency_key=key,
    ))
    subscription.status = ACTIVE
    subscription.updated_at = datetime.now(UTC)
    logger.info("%s %s -> ACTIVE", action, subscription.msisdn)
    return _reference("SIM", key)


def unblock_sim(session: Session, customer_id: str, key: str) -> str:
    """Unblock a BLOCKED line (idempotent)."""
    return _sim_case(session, customer_id, "UNBLOCK", key, allowed_from={BLOCKED})


def reactivate_sim(session: Session, customer_id: str, key: str) -> str:
    """Reactivate a SUSPENDED (or BLOCKED) line. TERMINATED lines are refused."""
    return _sim_case(session, customer_id, "REACTIVATE", key, allowed_from={SUSPENDED, BLOCKED})


def replace_sim(session: Session, customer_id: str, sim_type: str, key: str) -> str:
    """Order a replacement SIM and record the provisioning request (idempotent)."""
    if _existing_request(session, key) is not None:
        return _reference("SIM", key)

    normalized = sim_type if sim_type in ("physical", "esim") else "physical"
    subscription = _subscription(session, customer_id)
    if subscription.status == TERMINATED:
        raise ProvisioningError("cannot replace the SIM of a terminated line")

    tracking = f"TRK-{uuid.uuid4().hex[:8].upper()}"
    session.add(SimOrder(
        customer_id=subscription.customer_id, subscription_id=subscription.id,
        sim_type=normalized, status="requested", tracking_code=tracking,
    ))
    session.add(ProvisioningRequest(
        subscription_id=subscription.id, customer_id=subscription.customer_id,
        action_type="REPLACE_SIM", status="completed", idempotency_key=key,
        parameters={"sim_type": normalized, "tracking_code": tracking},
        completed_at=datetime.now(UTC),
    ))
    logger.info("REPLACE_SIM %s (%s) tracking=%s", subscription.msisdn, normalized, tracking)
    return _reference("SIM", key)


# ---------------- plan catalog ----------------
def _resolve_plan(session: Session, plan_code: str) -> str:
    """Resolve a caller/model-supplied plan to a real, active catalog entry.

    The catalog is reference.products, not a hardcoded list: a hardcoded set drifts from the
    products actually sold, and refuses plans that legitimately exist (or accepts ones that do
    not). Matching accepts either the product_code ("FLEXI") or the display name ("Postpaid
    Flexi"), case-insensitively, because the caller says the name while the system stores a code.

    The value written to crm.subscriptions.plan_code is whatever the existing rows already use for
    that product, so this never introduces a second vocabulary into the same column.
    """
    from persistence.models.reference import Product

    wanted = (plan_code or "").strip()
    if not wanted:
        raise ProvisioningError("no plan was specified")

    products = list(session.scalars(select(Product).where(Product.active.is_(True))))
    if not products:
        raise ProvisioningError("the product catalog is empty; cannot validate a plan change")

    needle = wanted.casefold()
    for product in products:
        if needle in ((product.product_code or "").casefold(), (product.name or "").casefold()):
            # Subscriptions in this deployment store the product NAME in plan_code; follow whatever
            # the catalog row calls it so both stay in one vocabulary.
            return product.name or product.product_code

    available = ", ".join(sorted(f"{p.name} ({p.product_code})" for p in products))
    raise ProvisioningError(f"unknown plan {plan_code!r}; available plans: {available}")


# ---------------- Subscription changes ----------------
def change_plan(session: Session, customer_id: str, plan_code: str, key: str) -> str:
    """Move the subscription to ``plan_code`` and record the history row (idempotent)."""
    if _existing_request(session, key) is not None:
        return _reference("PLN", key)

    wanted = _resolve_plan(session, plan_code)
    subscription = _subscription(session, customer_id)
    if subscription.status == TERMINATED:
        raise ProvisioningError("cannot change the plan of a terminated line")
    if subscription.plan_code == wanted:
        raise ProvisioningError(f"the line is already on {wanted}")

    previous = subscription.plan_code
    session.add(PlanChangeHistory(
        subscription_id=subscription.id, from_plan=previous, to_plan=wanted,
        changed_by="agent", effective_date=date.today(),
    ))
    session.add(ProvisioningRequest(
        subscription_id=subscription.id, customer_id=subscription.customer_id,
        action_type="CHANGE_PLAN", status="completed", idempotency_key=key,
        parameters={"from_plan": previous, "to_plan": wanted},
        completed_at=datetime.now(UTC),
    ))
    subscription.plan_code = wanted
    subscription.updated_at = datetime.now(UTC)
    logger.info("CHANGE_PLAN %s %s -> %s", subscription.msisdn, previous, wanted)
    return _reference("PLN", key)


def set_roaming(session: Session, customer_id: str, enable: bool, key: str) -> str:
    """Enable or disable roaming on the subscription (idempotent)."""
    if _existing_request(session, key) is not None:
        return _reference("ROAM", key)

    subscription = _subscription(session, customer_id)
    if subscription.status != ACTIVE:
        raise ProvisioningError(
            f"cannot change roaming: the line is {subscription.status}, expected ACTIVE"
        )
    if bool(subscription.roaming_enabled) == bool(enable):
        raise ProvisioningError(
            f"roaming is already {'enabled' if enable else 'disabled'} on this line"
        )

    session.add(ProvisioningRequest(
        subscription_id=subscription.id, customer_id=subscription.customer_id,
        action_type="ACTIVATE_ROAMING", status="completed", idempotency_key=key,
        parameters={"enable": bool(enable)}, completed_at=datetime.now(UTC),
    ))
    subscription.roaming_enabled = bool(enable)
    subscription.updated_at = datetime.now(UTC)
    logger.info("ROAMING %s -> %s", subscription.msisdn, bool(enable))
    return _reference("ROAM", key)


# ---------------- read model ----------------
def get_subscription_state(session: Session, customer_id: str) -> dict:
    """Project the line's provisioning-relevant state (verification and diagnostics)."""
    subscription = _subscription(session, customer_id)
    return {
        "customer_id": customer_id,
        "subscription_id": str(subscription.id),
        "msisdn": subscription.msisdn,
        "status": subscription.status,
        "plan_code": subscription.plan_code,
        "roaming_enabled": bool(subscription.roaming_enabled),
    }
