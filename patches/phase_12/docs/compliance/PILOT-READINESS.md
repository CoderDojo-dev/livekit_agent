# Pilot Readiness Checklist (Blueprint section 21)

The platform is ready for a controlled pilot when **every** item holds on one build in staging.

## Built & verified (this repo)
- [x] Canonical UUID identity model end to end; MSISDN resolved once at the edge.
- [x] Every sensitive action: deterministic **verdict → idempotent action → hash-chained audit**.
- [x] Domain write effects (payments / plans / recharges / SIM cases) atomic with the ledger.
- [x] Durable conversation record (sessions / turns / sentiment / escalations / callbacks), off the voice path.
- [x] Ticketing mirror + notification log durable.
- [x] **Consent flow audited** — `crm.consent_records` + an `audit_ledger` 'consent' entry.
- [x] **Retention/purge** — audited job; transcripts anonymized + audio pointers cleared at the boundary.
- [x] Reference catalogs + business-api (§17) + supervisor dashboard answering "why was this refused?".
- [x] Cross-domain integrity + audit-chain verification job passes.
- [x] OTel pipeline (TTFA/TTFT export) + collector.
- [x] Multilingual UAT (FR/AR/EN) automated for the deterministic layers.
- [x] Load + soak scripts wired as gates.

## Must pass in staging before pilot sign-off (needs the live stack)
- [ ] Full spoken UAT in FR/AR/EN for every CDC §5 scenario (UAT-PLAN.md), incl. turn-detection per language.
- [ ] Resilience chaos test: STT/LLM/TTS primary-failure fallback, once per language, no dropped call.
- [ ] Load test green against the sub-second TTFA budget under realistic concurrency.
- [ ] Soak test: no resource/state bleed across a long sequential-call run.
- [ ] Least-privilege DB roles (§19) granted; append-only enforced; PII-map isolated to compliance.
- [ ] Live connector bindings confirmed (OCS / Billing / Payment / SMS / GLPI) with `CONNECTOR_MODE`.
- [ ] Retention window + export/delete workflow validated against the agreed compliance policy.

When every box is checked on the same staging build, the pilot plan is approved.