-- Normalize crm.subscriptions.plan_code from display names to catalog product_code.
--
-- Before: plan_code held the display NAME ("Postpaid Flexi") in a column named plan_code.
-- After:  plan_code holds the catalog product_code ("FLEXI"); the display name is resolved from
--         reference.products at read time (context-service snapshot).
--
-- Idempotent: only rows whose plan_code equals a product NAME are converted. Once converted
-- (plan_code = product_code) they no longer match a name, so re-running is a no-op.
--
-- Run after `alembic upgrade head` and the reference seed, e.g.:
--   docker compose exec -T postgres psql -U telecom -d telecom -f - < repair_plan_code.sql

UPDATE crm.subscriptions AS s
SET    plan_code = p.product_code
FROM   reference.products AS p
WHERE  lower(s.plan_code) = lower(p.name)
  AND  s.plan_code <> p.product_code;

-- Verify: every active subscription's plan_code is now a known product_code.
--   SELECT s.msisdn, s.plan_code
--   FROM crm.subscriptions s
--   LEFT JOIN reference.products p ON lower(p.product_code) = lower(s.plan_code)
--   WHERE s.deleted_at IS NULL AND p.product_code IS NULL;
--   -- expected: 0 rows
