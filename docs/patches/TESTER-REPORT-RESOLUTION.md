# Tester Report — Resolution Summary (all items)

Four grouped patch-sets. Legend: ✅ done + offline-verified · 🔌 real code, **binds at integration**
via `.env`/config · 🏗 staging gate (needs the live stack) · ✔︎ already fixed before the report snapshot.

## Patch-Set 1 — Security & hygiene
- ✅ #15 CORS allow-list (token + business-api) · #16 creds→env · #17 service-to-service auth
  (opt-in `INTERNAL_API_KEY`) · #21 healthchecks · #13 DB pool config · #9/#27 AccountServicesAgent on
  BaseTelecomAgent · #24 .gitignore · #25 mypy · #26 ruff.
- ✔︎ #12 dead code (removed in Persistence P1) · #31 chaos test (already passes).
- ➕ full `.env.example` with every API/link/connector placeholder.

## Patch-Set 2 — Persistence completeness
- ✅ #1 OSS schema · #2 Provisioning schema (exercised by CHANGE_PLAN/ACTIVATE_ROAMING projections) ·
  #14 JSONB GIN indexes (migration 0008) · #29 migration tests.
- 📎 #28 patches-dir typo = local artifact (rename on your machine).

## Patch-Set 3 — Real integrations behind CONNECTOR_MODE
- 🔌 #3 integration-adapters (billing/OCS/payment/CRM/NMS/ticketing: Mock+Live+factory) ·
  #4 GLPI REST client + factory · #5 Twilio SMS/WhatsApp + SMTP email + factory ·
  #10 execution dispatch via adapters · #11 notification-client (real HTTP) · messaging-gateway MCP.
  All mock-by-default; live binds via `.env`.

## Patch-Set 4 — Infra, storage & ops
- 🔌 #6 Qdrant retriever (lexical fallback) · #7 Redis cache (NullCache default) · #8 MinIO storage
  (NullStore default; retention blob purge).
- ✅ #30 Dockerfiles (×11) · #18 API gateway (nginx) · #19 CI/CD (GitHub Actions) · #20 Helm chart ·
  #22 backup/restore + audit-verify · #23 secrets management.

## Remaining = staging sign-off (not code)
🏗 Spoken FR/AR/EN UAT for every CDC §5 scenario · resilience chaos (STT/LLM/TTS fallback) under load ·
TTFA load gate + soak on the voice path · least-privilege DB role grants (§19) · confirming each live
connector (`CONNECTOR_MODE=live`). These need the live LiveKit + provider + legacy-system stack; see
`docs/compliance/PILOT-READINESS.md`.

## Verification snapshot
**70 offline tests green** across the platform after all four patch-sets; vendor boundary clean;
33 tables / 12 schemas / 8 migrations; every new integration mock-by-default and gated.
