# Telecom AI Voice Agent Platform

Self-hosted, open-source **LiveKit** platform that autonomously handles frequent telecom
customer requests over real-time **voice and text** in **French (primary), Arabic, English**,
applies **deterministic business rules** before any sensitive action, executes real actions
(payment, SIM unblock, ticket creation), and escalates to a human with a full dossier when
needed. AI inference (STT/LLM/TTS) is cloud; everything touching PII, audit and business
systems is self-hosted.

## Layout (Blueprint section 11)
- `apps/` — independently deployable apps (agent-worker, business-api, token-service, dashboards, widget)
- `services/` — domain microservices (context, knowledge, decision, policy, execution, notification)
- `mcp-servers/` — internal MCP server (knowledge + GLPI, low-risk reads)
- `packages/` — shared libraries (domain-core, integration-adapters, audit-trail, pii-shield, notification-client, observability-kit)
- `infra/` — docker-compose, helm, livekit config, ci-cd
- `docs/` — architecture blueprint, ADRs, decision records

## Architecture rules (non-negotiable)
1. Clean/Hexagonal + DDD + SOLID. Business rules never import LiveKit/vendor SDKs — they sit behind ports in `packages/domain-core`.
2. `apps/agent-worker/src/server.py` is a **composition root only** (wiring; zero business logic).
3. The real-time layer holds no business logic — tools are thin facades calling domain services via typed clients.
4. Deterministic Policy returns `AUTHORIZED / REFUSED / ESCALATE` + rule-id + justification before every action, never bypassable, written to the hash-chained audit ledger.
5. No sensitive-action path skips Decision -> Policy -> Execution. Sensitive actions are idempotent.
6. Direct LiveKit provider plugins + `FallbackAdapter` (never LiveKit Inference). FR/AR/EN only.

## Quick start (infra only; agent feature wiring lands in later phases)
```bash
cp .env.example .env
make up        # bring up livekit-server, redis, postgres, qdrant, minio, otel-collector
make down
```

## Roadmap status
- Phase 0 — Verification & Decision Gate: DONE (`docs/architecture/phase-0-verification-gate/`)
- Phase 2 — Modular Scaffolding: THIS TREE
- Phase 1/3+ — pipeline, context, knowledge, policy, execution, escalation, frontend, observability: next