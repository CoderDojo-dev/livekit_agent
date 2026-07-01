# Phase 12 (final) — Compliance, Multilingual QA & Pilot

The readiness phase: consent is now audited, retention/purge is an audited job, the multilingual
behaviour is asserted in FR/AR/EN, load/soak gates exist, and the traceability matrix + pilot
checklist give a sign-off artifact. This closes the Blueprint §10 roadmap.

## What shipped (14 files)
- **Consent flow audited (§8.1)** — `ConsentTask.record_consent` now persists a `crm.consent_records`
  row **and** writes an `audit_ledger` `consent` entry (via the conversation writer, off the voice
  path). The deferred "consent-event persistence" note in the task is now done.
- **Retention/purge job (§8.3)** — `business-api/jobs/retention.py`: at the retention boundary it
  anonymizes transcripts (`[purged]`) and clears audio pointers, **writes an audit entry** (never an
  ad-hoc DELETE), and supports `dry_run`. Exposed at `POST /api/v1/jobs/retention` (administrateur,
  dry_run=true by default).
- **Multilingual UAT (FR/AR/EN)** — automated for the deterministic layers: notification templates
  render in all three languages (and Arabic is genuinely localized, not an English fallback); the
  sentiment scorer detects negativity and escalates in French, Arabic, **and** English. Plus
  `docs/compliance/UAT-PLAN.md` — the CDC §5 × {FR,AR,EN} scenario matrix for the manual voice UAT.
- **Load + soak gates (§20)** — `tests/load/loadtest.py` (p95 vs latency budget) and `soak.py`
  (RSS growth across a long sequential run); both exit non-zero on failure for CI/staging.
- **Sign-off artifacts** — `docs/compliance/TRACEABILITY.md` (CDC → component → phase → status) and
  `docs/compliance/PILOT-READINESS.md` (what's built vs what must pass in staging before pilot).

## Run
```bash
# retention (safe dry-run first)
curl -X POST -H 'X-Role: administrateur' "http://localhost:8108/api/v1/jobs/retention?retention_days=90&dry_run=true"

# multilingual UAT
( cd apps/agent-worker && PYTHONPATH=src python -m pytest -q tests/uat )
( cd services/notification-service && PYTHONPATH=src python -m pytest -q tests/test_multilingual.py )

# load + soak (services running)
pip install httpx psutil
python tests/load/loadtest.py --url http://localhost:8108/api/v1/kpis --requests 500 --concurrency 25 --budget-ms 250
python tests/load/soak.py     --url http://localhost:8108/health --iterations 5000
```

## Verification
Full-platform offline sweep — **49 tests green**: obs-kit 2, audit-trail 3, context 4, policy 10,
execution 5, notification 6, ticketing 2, business-api 7, agent-worker 10. Vendor boundary clean.
Consent + retention DB writes are exercised against Postgres on the dev machine.

## Honest caveats (what staging must finish)
Per `PILOT-READINESS.md`, sign-off needs the live stack for the things a sandbox can't prove: the full
**spoken** FR/AR/EN UAT incl. turn-detection per language, the resilience chaos test (STT/LLM/TTS
fallback), the TTFA load gate under real concurrency, the soak run on the voice path, the §19
least-privilege role grants, and the live connector bindings (`CONNECTOR_MODE`). The automated suites
make the deterministic half checkable on every PR; the voice half is the staging gate.

---

## Roadmap complete (Phases 1–12 + Persistence P1–P6)
The platform is feature-complete against the Blueprint: a self-hosted, multilingual (FR/AR/EN),
voice-first telecom support agent where every sensitive action is **verdict-checked, idempotent, and
hash-chain audited**; identity is canonical UUIDs resolved once at the edge; the full data layer is
real PostgreSQL (27 tables / 12 schemas / 6 migrations); operators get OTel telemetry + a supervisor
dashboard that answers *"why was this refused?"*; and compliance (consent, retention, audit) is
durable and demonstrable. What remains is the staging/pilot sign-off in `PILOT-READINESS.md` and the
⚠-bind-at-integration live connectors — config, not code.
