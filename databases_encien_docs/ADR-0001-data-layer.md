# ADR-0001 — Persistence & Data Layer (my analysis of your spec + the adapted plan)

## Verdict on your document
It's genuinely strong — better organized than most production specs. I'm adopting the spine of it
**verbatim**, and adapting a few things to fit what our system actually does. Below is the honest cut.

## Adopted exactly as written
- **The canonical identity model (§1)** — this is the single best decision in the document. Two UUID
  keys (`customer_id`, `subscription_id`); **MSISDN is a UNIQUE attribute of `subscriptions`,
  resolved once at the edge, never a join key.** This removes the "join sometimes on msisdn,
  sometimes on customer_id" ambiguity for good. Implemented, with the `/internal/context/resolve`
  resolver (§16.2) as the one place the translation happens.
- **One database, schema-per-bounded-context (§2.1)** with least-privilege roles (§19). Keeps real
  FKs/transactions while preserving module boundaries. All 12 schemas are created in migration 0001.
- **Polyglot split (§2)** — Postgres truth / Redis cache / Qdrant vectors / MinIO blobs.
- **Safety core (§12)** append-only + hash-chained audit — matches what we already built in-memory.
- **`national_id` carries the CIN** (closes review note 4); naming authority `first_name`/`last_name`,
  `preferred_language` (live-system wins).
- **Alembic + SQLAlchemy**, adapter **mock→live** switch as a config flag (§16.6), money as `NUMERIC`.

## Adapted — and why (my genuine pushback)
1. **Build the tables the running system actually exercises; scaffold the rest.** The spec models
   ~40 tables across 12 schemas, but the agent today only reads/writes a subset. I implement the
   **agent-touched** tables slice by slice and create the other schemas empty, to be filled when a
   use case arrives. Standing up ~12 domains the code never calls (full OSS/NMS, provisioning depth,
   disputes/refunds/collections, vouchers, eSIM inventory) would be **unmeasurable dead schema** —
   the opposite of your "everything measurable, made the correct way." This is the most important
   adaptation.
2. **I would NOT move all live session state to Redis (§14).** For a single-owner, per-call voice
   session, in-process state is lower-latency and simpler. Redis earns its place for the
   Customer-360 **prefetch cache**, the **idempotency** dedupe, and cross-worker handoff — not the
   hot per-turn counters. Plan: keep live turn state in-process; persist the **durable** conversation
   record (sessions/turns/sentiment) to Postgres **asynchronously, off the voice path**; add Redis as
   a cache when horizontal scale demands it. Postgres stays the source of truth either way.
3. **Conversation persistence is async, never inline in a turn** — the worker is real-time; a
   synchronous DB write per turn would add latency to voice-to-voice. Writes happen at turn
   boundaries / call end through a non-blocking writer.
4. **Sync SQLAlchemy for the services** (not async). FastAPI threadpools sync path-ops; the latency
   path is HTTP, not the DB driver. Simpler and easier to get right than async sessions.
5. **Index names** follow SQLAlchemy's convention rather than the spec's `idx_*` literals —
   functionally identical; nothing depends on the string.

## Sequenced plan (each slice runnable + measurable)
- **P1 (this slice): CRM/Billing/OCS read foundation.** `packages/persistence` (engine/session/Base),
  crm+billing+ocs models, Alembic initial migration (extensions, 12 schemas, trigger, tables,
  `v_subscription_live` view), Postgres compose, pilot seed, and **context-service fully on Postgres**
  + the identity resolver. The agent's entire READ path is now real Postgres.
- **P2: Safety core.** Persist `policy.policy_verdicts`, `execution.action_ledger`,
  `audit.audit_ledger` (+ `pii_token_map`); swap policy-service, execution-service, and the
  `audit-trail` package from in-memory to Postgres. Idempotency key carried end-to-end.
- **P3: Conversation + write paths.** `conversation.*` (async writer), `billing.payments`/
  `payment_plans`, `ocs.recharges`/`usage`, `sim.*` write tables, ticketing mirror, notification log.
- **P4: Reference + back-office.** `reference.*` catalogs (incl. versioned business rules consumed by
  policy), `business-api` endpoints (§17), the cross-domain integrity + audit-chain job (§20), then
  Redis cache + Qdrant wiring.
- **⚠ Live bindings stay mock** behind the same ports until integration time (§16): OCS, billing core,
  payment gateway, SMS/WhatsApp, GLPI. Flipping `CONNECTOR_MODE` is the only change — no schema/query change.
