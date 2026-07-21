"""Seed the pilot dataset (real TND, the three canonical callers) — idempotent.

FKs are resolved through ORM relationships (assign objects, never hardcode UUIDs across rows),
exactly as spec section 20 requires. Run after `alembic upgrade head`:
    DATABASE_URL=... python -m seed.seed_pilot
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.billing import Account, Invoice
from persistence.models.crm import Customer, Subscription
from persistence.models.ocs import BalanceAccount

TODAY = date.today()


def _activation(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


def seed() -> None:
    """Insert the three pilot customers and their lines/invoices/balances if not present."""
    with session_scope() as session:
        if session.scalar(select(Customer).where(Customer.national_id == "11224087")):
            print("pilot already seeded - nothing to do")
            return

        # --- Amine Ben Salah (fr, postpaid, not VIP) ---
        amine = Customer(
            national_id="11224087", first_name="Amine", last_name="Ben Salah",
            email="choiyebsaad2000@gmail.com", contact_number="+21626078277",
            preferred_language="fr",
            segment="postpaid_flexi", vip_flag=False, fraud_suspected=False,
            city="Tunis", region="Tunis", status="active",
        )
        amine_sub = Subscription(
            customer=amine, msisdn="+21620155320", plan_type="POSTPAID",
            plan_code="Postpaid Flexi", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(1420),
        )
        amine_acct = Account(
            customer=amine, account_number="BA-000021", account_type="postpaid",
            billing_cycle_day=10, payment_terms_days=15, currency_code="TND", status="active",
        )
        amine_inv = Invoice(
            account=amine_acct, customer=amine, invoice_number="INV-2026-04-100021",
            period_start=date(2026, 4, 1), period_end=date(2026, 4, 30),
            issue_date=date(2026, 5, 1), due_date=date(2026, 7, 10),
            subtotal=36.000, tax_amount=6.500, total_amount=42.500, outstanding_amount=42.500,
            currency_code="TND", status="issued",
        )

        # --- Yousra Trabelsi (ar, prepaid, VIP) ---
        yousra = Customer(
            national_id="33449912", first_name="Yousra", last_name="Trabelsi",
            email="chouaibsaad.contact@gmail.com", contact_number="+21626078277",
            preferred_language="ar",
            segment="prepaid_trankil", vip_flag=True, fraud_suspected=False,
            city="Sousse", region="Sousse", status="active",
        )
        yousra_sub = Subscription(
            customer=yousra, msisdn="+21629744108", plan_type="PREPAID",
            plan_code="Prepaid Mobile", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(305),
        )
        yousra_main = BalanceAccount(
            subscription=yousra_sub, customer=yousra, balance_type="main",
            balance_value=7.300, balance_unit="TND", expiry_date=date(2026, 7, 5), status="active",
        )
        yousra_data = BalanceAccount(
            subscription=yousra_sub, customer=yousra, balance_type="data",
            balance_value=1840, balance_unit="MB", expiry_date=date(2026, 7, 5), status="active",
        )

        # --- Karim Gharbi (en, postpaid fibre, not VIP, overdue) ---
        karim = Customer(
            national_id="55662256", first_name="Karim", last_name="Gharbi",
            email="ws0461646@gmail.com", contact_number="+21626078277",
            preferred_language="en",
            segment="fiber_home", vip_flag=False, fraud_suspected=False,
            city="Ariana", region="Ariana", status="active",
        )
        karim_sub = Subscription(
            customer=karim, msisdn="+21652310977", plan_type="POSTPAID",
            plan_code="Fibre Fixe", status="ACTIVE", roaming_enabled=False,
            activation_date=_activation(88),
        )
        karim_acct = Account(
            customer=karim, account_number="BA-000078", account_type="postpaid",
            billing_cycle_day=20, payment_terms_days=15, currency_code="TND", status="dunning",
        )
        karim_inv = Invoice(
            account=karim_acct, customer=karim, invoice_number="INV-2026-04-100078",
            period_start=date(2026, 4, 1), period_end=date(2026, 4, 30),
            issue_date=date(2026, 5, 1), due_date=date(2026, 6, 20),
            subtotal=62.000, tax_amount=11.900, total_amount=73.900, outstanding_amount=73.900,
            currency_code="TND", status="overdue",
        )

        session.add_all(
            [amine, amine_sub, amine_acct, amine_inv,
             yousra, yousra_sub, yousra_main, yousra_data,
             karim, karim_sub, karim_acct, karim_inv]
        )
        print("seeded 3 customers, 3 subscriptions, 2 invoices, 2 balances")


if __name__ == "__main__":
    seed()