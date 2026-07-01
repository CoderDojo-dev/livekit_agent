# Traceability Matrix — CDC → Architecture → Phase → Status (Blueprint section 21)

The pilot-readiness sign-off artifact: every requirement maps to a component, the phase that built it,
and how it is verified. "DB-integration" = exercised against Postgres on the developer machine.

| CDC | Requirement | Component(s) | Phase | Verification | Status |
|---|---|---|---|---|---|
| §4 | Canonical identity (MSISDN→UUID once) | context-service `/internal/context/resolve`; crm.* | P1 | mapping tests + DB-integration | ✅ |
| §5.1 | Invoice consultation | context-service; billing.invoices | P1 | mapping tests + DB | ✅ |
| §5.2 | Balance consultation | context-service; ocs.balance_accounts | P1 | mapping tests + DB | ✅ |
| §5.3 | Payment deferral (gated) | policy + execution; billing.payment_plans | P2, P4 | policy 10 + projection tests + DB | ✅ |
| §5.4 | Payment (idempotent, capped) | execution; billing.payments | P2, P4 | executor/projection tests + DB | ✅ |
| §5.5 | SIM unblock (identity-gated) | execution; sim.block_unblock_cases | P4 | projection tests + DB | ✅ |
| §5.6 | Prepaid top-up | execution; ocs.recharges | P4 | projection tests + DB | ✅ |
| §5.9 | Ticketing (GLPI mirror) | ticketing MCP; ticketing.tickets | P5 | mirror tests + DB | ✅ |
| §6 | Deterministic policy + audit | policy-service; policy.policy_verdicts; audit ledger | P2 | policy 10 + chain 3 | ✅ |
| §6.5 | Step-up identity verification | context-service verify (national_id last-4) | P1 | mapping tests | ✅ |
| §7 | Escalation to human/manager | escalation tools; conversation.escalation_cases | P3 | writer tests + DB | ✅ |
| §8.1 | Recording consent (audited) | ConsentTask; crm.consent_records + audit | P12 | consent persists + audit entry (DB) | ✅ |
| §8.3 | Retention / purge (audited) | business-api jobs/retention | P12 | cutoff test + DB-integration | ✅ |
| §8.4 | Hash-chained tamper-evident audit | audit-trail PgAuditLedger; audit.audit_ledger | P2 | chain + tamper tests | ✅ |
| §9.1 | Supervisor/Admin dashboard | supervisor-dashboard + business-api | P6, P11 | tsc + vite build; endpoint tests | ✅ |
| §9.2 | KPIs (containment/escalation/...) | business-api /kpis | P6 | kpi tests + DB | ✅ |
| §9.3 | Cross-domain integrity job | business-api jobs/integrity | P6 | summarize test + query compile + DB | ✅ |
| §10.1 | Sub-second TTFA budget | metrics_hook + OTel ttfa histogram | P11 | OTel export; load gate | ⚠ staging |
| §13 | Multilingual FR/AR/EN | templates; sentiment; turn-detection | P12 | multilingual UAT suites | ✅ (voice UAT manual) |
| §15 | Resilience / fallback | FallbackAdapter (providers) | P3(core) | chaos tests | ⚠ staging |
| §16 | Observability (OTel) | observability-kit; OTel collector | P11 | no-op tests; live collector | ✅ |
| §14/§19 | Least-privilege DB roles | spec section 19 grants | P2–P6 | ⚠ ops hardening at deploy | ⚠ bind |

Legend: ✅ built + verified (offline + DB-integration on dev) · ⚠ staging/ops = needs the live
staging stack (concurrency, real providers, role grants) to fully sign off.