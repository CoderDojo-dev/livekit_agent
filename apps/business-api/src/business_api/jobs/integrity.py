"""Cross-domain referential integrity + audit-chain verification job (spec section 20.4).

Every domain customer_id/subscription_id must resolve in crm; and the audit hash-chain must verify.
FKs already enforce the former at write time - this job is defense-in-depth + catches out-of-band data.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from audit_trail import PgAuditLedger
from persistence.models.billing import Account, Invoice
from persistence.models.conversation import CallSession
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount


@dataclass
class IntegrityReport:
    """Result of an integrity run."""

    orphans: dict
    audit_chain_intact: bool
    audit_entries: int

    @property
    def ok(self) -> bool:
        return self.audit_chain_intact and not any(self.orphans.values())


def summarize(orphans: dict, audit_chain_intact: bool) -> bool:
    """Pure helper: overall pass/fail from orphan counts + chain status."""
    return audit_chain_intact and not any(orphans.values())


def _orphans(session: Session, child_model, fk_attr, parent_model) -> int:
    """Count child rows whose (non-null) FK does not resolve in the parent table."""
    stmt = (
        select(func.count())
        .select_from(child_model)
        .where(fk_attr.is_not(None), fk_attr.not_in(select(parent_model.id)))
    )
    return session.scalar(stmt) or 0


def run_integrity(session: Session) -> IntegrityReport:
    """Run the cross-domain orphan checks + the audit-chain verification."""
    orphans = {
        "billing.accounts->crm.customers": _orphans(session, Account, Account.customer_id, Customer),
        "billing.invoices->crm.customers": _orphans(session, Invoice, Invoice.customer_id, Customer),
        "ocs.balance_accounts->crm.subscriptions": _orphans(
            session, BalanceAccount, BalanceAccount.subscription_id, Subscription
        ),
        "conversation.call_sessions->crm.customers": _orphans(
            session, CallSession, CallSession.customer_id, Customer
        ),
    }
    ledger = PgAuditLedger(session)
    return IntegrityReport(orphans=orphans, audit_chain_intact=ledger.verify(), audit_entries=ledger.count())