-- Refresh the two threshold-bearing registry rows so their definition_json names the governing
-- POLICY_* env var instead of a stale literal. The live numbers are supplied by the business-api
-- overlay (business_api.policy_view) from the same env the policy engine enforces.
--
-- Needed because the reference seed is insert-only-if-absent: an already-seeded DB still holds the
-- old {"max_payment_tnd": 200} literal, which this brings in line with a fresh seed.
--
-- Idempotent: running twice sets the same JSON. Run after the reference seed, e.g.:
--   docker compose exec -T postgres psql -U telecom -d telecom -f - < repair_business_rules_definition.sql

UPDATE reference.business_rules
SET    definition_json = '{"governed_by": ["POLICY_PAYMENT_CAP_TND"]}'::jsonb
WHERE  rule_id = 'RULE_BILLING_CAP';

UPDATE reference.business_rules
SET    definition_json = '{"governed_by": ["POLICY_DEFERRAL_MIN_AGE_DAYS", "POLICY_DEFERRAL_MAX_PER_YEAR", "POLICY_DEFERRAL_UNPAID_THRESHOLD_TND"]}'::jsonb
WHERE  rule_id = 'RULE_DEFERRAL_ELIGIBILITY';
