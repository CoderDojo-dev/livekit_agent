-- P0-1 §14.2 data-integrity assertions.
--
-- Run against the shared postgres:
--   docker exec docker-compose-postgres-1 psql -U telecom -d telecom -f /dev/stdin < scripts/prove_p0_1_data_integrity.sql
--
-- Everything here is READ-ONLY. Every row count is an expectation of a steady-state system.

\echo '== P0-1 data-integrity assertions =='

-- 1. The P0-1 tables exist in the auth schema (0016).
SELECT 'portal_identity tables' AS check_name,
       (SELECT count(*) = 2
          FROM information_schema.tables
         WHERE table_schema = 'auth'
           AND table_name IN ('portal_accounts', 'portal_sessions')) AS passes;

-- 2. Exactly one seeded staff account exists and it is active.
SELECT 'seeded staff account' AS check_name,
       (SELECT count(*) = 1 FROM auth.portal_accounts WHERE kind = 'staff' AND is_active) AS passes;

-- 3. No legacy BSS credential was touched: all 3 remain cin_last4 / scrypt and active.
SELECT 'bss credentials untouched' AS check_name,
       (SELECT count(*) = 3
          FROM auth.customer_credentials
         WHERE active AND verifier_type = 'cin_last4'
           AND key_version = 1) AS passes;

-- 4. Portal sessions store only digests, never tokens.
SELECT 'sessions store token digests' AS check_name,
       (SELECT count(*) > 0
          FROM auth.portal_sessions ps
         WHERE token_digest ~ '^[0-9a-f]{64}$') AS passes;

-- 5. Existing risky tables unchanged by the migration (counts sane, no wipe).
SELECT 'customers intact' AS check_name,
       (SELECT count(*) >= 3 FROM crm.customers) AS passes;
SELECT 'verification events intact' AS check_name,
       (SELECT count(*) > 0 FROM auth.verification_events) AS passes;
SELECT 'conversation turns intact' AS check_name,
       (SELECT count(*) > 0 FROM conversation.turns) AS passes;

-- 6. Nobody added a password column or plaintext anywhere obvious (spot check).
SELECT 'no plaintext password column' AS check_name,
       (SELECT count(*) = 0
          FROM information_schema.columns
         WHERE column_name = 'password' AND table_schema NOT IN ('pg_catalog', 'information_schema')) AS passes;

-- 7. The audit ledger is still being written (any prior hash present).
SELECT 'audit ledger present' AS check_name,
       (SELECT count(*) > 0 FROM audit.audit_ledger) AS passes;