"""Seed the reference catalogs (spec section 13.1) - idempotent. Run after `alembic upgrade head`:
    DATABASE_URL=... python -m seed.seed_reference
"""
from __future__ import annotations

from sqlalchemy import select

from persistence.engine import session_scope
from persistence.models.reference import BusinessRule, ErrorCatalog, Product, RechargeCatalog

# The deterministic engine still executes these rules in code; this table is the versioned,
# auditable registry the business-api exposes (governance), mirroring the engine's rule_ids.
RULES = [
    ("RULE_BILLING_CAP", "billing", "Agent may not authorize a payment above the per-call cap.",
     {"max_payment_tnd": 200}),
    ("RULE_DEFERRAL_ELIGIBILITY", "billing",
     "Deferral requires verified identity, minimum account age, and within the yearly cap.",
     {"min_account_age_days": 180, "max_deferrals_per_year": 2}),
    ("RULE_IDENTITY_REQUIRED", "identity", "Sensitive actions require step-up identity verification.", {}),
    ("RULE_FRAUD_BLOCK", "fraud", "Fraud-suspected accounts cannot perform sensitive actions; escalate.", {}),
    ("RULE_VIP_ESCALATION", "escalation", "VIP callers escalate to a manager for sensitive actions.", {}),
    ("OUT_PII", "guardrail", "Outbound responses must not leak PII (national id / full msisdn).", {}),
]
ERRORS = [
    ("POLICY_NO_VERDICT_ID", "policy", "Action non autorisee : verdict manquant.",
     "الاجراء غير مصرح به: لا يوجد قرار", "Action not authorized: missing verdict."),
    ("DECISION_LOW_CONFIDENCE", "decision", "Je prefere vous orienter vers un conseiller.",
     "سأحولك الى مستشار", "Routing you to a human advisor."),
]
PRODUCTS = [("FLEXI", "Postpaid Flexi", "POSTPAID"), ("TRANKIL", "Prepaid Mobile", "PREPAID"),
            ("FIBER", "Fibre Fixe", "POSTPAID")]
RECHARGES = [("R5", 5, 0), ("R10", 10, 1), ("R20", 20, 3), ("R50", 50, 10)]


def seed() -> None:
    with session_scope() as session:
        if session.scalar(select(BusinessRule).where(BusinessRule.rule_id == "RULE_BILLING_CAP")):
            print("reference already seeded - nothing to do")
            return
        for rule_id, domain, desc, definition in RULES:
            session.add(BusinessRule(rule_id=rule_id, domain=domain, description=desc,
                                     definition_json=definition, version=1, active=True))
        for code, domain, fr, ar, en in ERRORS:
            session.add(ErrorCatalog(code=code, domain=domain, message_fr=fr, message_ar=ar, message_en=en))
        for code, name, plan_type in PRODUCTS:
            session.add(Product(product_code=code, name=name, plan_type=plan_type, active=True))
        for code, amount, bonus in RECHARGES:
            session.add(RechargeCatalog(code=code, amount=amount, bonus_amount=bonus))
        print("seeded reference: 6 rules, 2 errors, 3 products, 4 recharges")


if __name__ == "__main__":
    seed()