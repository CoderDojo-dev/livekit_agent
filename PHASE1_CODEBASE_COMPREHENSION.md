# Phase 1 — Codebase comprehension report

> Read-only pass. **No source file was modified.** Every claim below is traced to a file I actually
> read; anything I could not prove from the repo is filed under §7 (open questions) rather than
> asserted.
>
> Tree state at time of writing: branch `version_90` @ `f6063f6`, in sync with `origin/version_90`
> and `gitlab/version_90`. **Zero tracked modifications**; the only working-tree entries are
> untracked docs (`patch-*.md`, `fixes/`, `fix_ticketing/`, `RAG knwoledge docs/`, `.opencode/`,
> `Frontend/admin_dashboard/package-lock.json`).

---

## 1. What the system is

A voice-first telecom customer-support platform: a LiveKit real-time agent takes the call, and every
consequential act (a decision, an authorisation, an execution, a notification) is written to
Postgres behind a **hash-chained audit ledger**. Two web frontends read that record — an admin/
supervision console and a customer portal.

The architecture's organising principle, visible in the code and not just the docs, is
**provability**: nothing that affects a customer is allowed to happen without a row that can later
be shown to a human. That principle is what most of the design decisions below are protecting.

## 2. Topology (verified against source, not docs)

| Component | Path | Port (from `uvicorn.run` / compose) |
| --- | --- | --- |
| context-service | `services/context-service` | 8101 |
| knowledge-service | `services/knowledge-service` | 8102 |
| decision-service | `services/decision-service` | 8103 |
| policy-service | `services/policy-service` | 8104 |
| execution-service | `services/execution-service` | 8105 |
| notification-service | `services/notification-service` | 8106 |
| token-service | `apps/token-service` | 8107 |
| business-api | `apps/business-api` | 8108 |
| ai-knowledge-rag (MCP) | `mcp-servers/ai-knowledge-rag` | 8201 |
| ticketing-glpi (MCP) | `mcp-servers/ticketing-glpi` | 8202 |
| messaging-gateway (MCP) | `mcp-servers/messaging-gateway` | 8203 |
| agent-worker | `apps/agent-worker` | LiveKit worker (no HTTP port of its own) |
| legacy simulators | `services/{ocs-billing-sim,nms-sim,provisioning-sim}` | host `8109/8110/8111` → container `8107/8108/8109` |

Shared libraries live in `packages/` (10 of them: `persistence`, `audit-trail`, `domain-core`,
`pii-shield`, `observability-kit`, `service-auth`, `cache`, `object-storage`,
`notification-client`, `integration-adapters`). `packages/persistence/src/persistence/models/__init__.py`
registers **16** model modules on `Base.metadata` for Alembic.

Two run modes, and the difference matters:

- **Host dev** — `Procfile` + honcho (`make dev`). Console scripts from each `[project.scripts]`,
  plus `python apps/agent-worker/src/server.py start` and the `apps/client-widget` Vite dev server.
- **Full Docker** — `infra/docker-compose/docker-compose.yml` + `docker-compose.apps.yml`.
  Inter-service URLs are overridden **in the compose file, not `.env`**, because `.env` is shared
  with host dev where `localhost` is correct. That comment is at the top of `docker-compose.apps.yml`
  and it explains a class of confusion you'd otherwise hit.

## 3. The call path

`token-service` mints a 15-minute LiveKit JWT with `roomJoin` only (`room_create=False`,
`can_update_own_metadata=False`) and, when `LIVEKIT_AGENT_NAME` is set, an explicit
`RoomAgentDispatch` so the right worker is summoned. The pilot MSISDN rides along as the
`telecom.caller_msisdn` attribute.

`apps/agent-worker` composes the media pipeline in `providers/session_factory.py` — and this file is
the one to respect: **it contains no vendor import**. STT/LLM/TTS/VAD/turn-detection each come from
a `providers/*` builder, each wrapped in a `FallbackAdapter([primary, secondary])` so one provider
outage does not drop the call. The stated rule is that `livekit.plugins` may not be imported outside
`apps/agent-worker/src/providers/` — that's a lint-enforceable boundary and worth keeping intact.

`config/settings.py` is pure twelve-factor with one genuinely good safety net:
`_distinct_service_urls()` refuses to boot if two services share an address, because the failure it
prevents ("the agent queries the wrong service and gets a valid but wrong answer") is invisible to
tests.

## 4. How the record is kept honest

**`ConversationWriter` (`apps/agent-worker/src/conversation/writer.py`)** — nothing touches the
voice path. Callers enqueue plain dicts in constant time; one background task drains the queue and
does sync SQLAlchemy writes in a thread. If Postgres is down the write is **logged and dropped** —
the call is never affected. Transcripts are PII-masked in the worker, before they leave it.

**`PgAuditLedger` (`packages/audit-trail/.../ledger.py`)** —
`entry_hash = sha256(previous_hash | canonical_json(payload) | timestamp)`. Appends serialise on
`pg_advisory_xact_lock(8472)`, and it **flushes rather than commits** so the business write and its
audit entry land in one transaction. `verify()` recomputes the whole chain, so a retroactive edit is
detectable rather than merely discouraged.

**`ExecutionService.execute()`** — the most carefully written function I read. In order: idempotency
key lookup (replay returns the original reference with `replay=True`); a pending `action_ledger`
insert whose UNIQUE key makes at-most-once hold *even under a race* (`IntegrityError` → re-lookup →
replay); four checks that the `PolicyVerdict` exists, is `AUTHORIZED`, matches the requested action,
and belongs to the same session; dispatch; audit. The domain projection then runs in a
`begin_nested()` **SAVEPOINT**, so a projection failure can never undo the ledger row or the audit
chain — it records `projection_failed` instead.

**`executor.dispatch()`** — mock by default with a deterministic prefixed reference, but it
**refuses** `EXECUTE_PAYMENT` / `TOP_UP` / `PAYMENT_DEFERRAL` in mock mode unless
`ALLOW_MOCK_SENSITIVE=1`, and in live mode an unmapped action raises `NotImplementedError` rather
than synthesising a reference that implies a real operation happened. Both are the honest choice.

## 5. Frontend security substrate (`Frontend/admin_dashboard`)

- `lib/api/business-api.ts` is **server-only**. The bearer token is read from the httpOnly session
  cookie inside that module; the browser never sees it. Since P0-1 the role is **never sent as a
  header** — the backend derives it from the token it issued, so no client can spoof one. The
  `role?` option survives only as documentation + edge-gating.
- `lib/api/middleware.ts` is *the* boundary: `authedMiddleware` / `requireRole(min)` attach to every
  server function, precisely because (per the TanStack Start auth guide) server functions are
  reachable independently of the route that renders them — a `beforeLoad` guard is not sufficient.
  `requireRole` mirrors `require_role()` in `business_api/security.py` so the UI fails at the edge
  with the same verdict instead of making a doomed round trip.
- Errors are normalised: FastAPI's `{"detail": …}` becomes `ApiError`, timeouts → 504, unreachable →
  503, malformed JSON → 502. No white screens by construction.
- Routing is TanStack Start file-based; `src/routes/README.md` explicitly forbids Next/Remix
  conventions (`src/pages/`, `app/layout.tsx`) and `routeTree.gen.ts` is generated.
- `AGENTS.md` warns the dashboard is Lovable-connected: **do not rewrite published history**
  (no force-push, rebase, amend or squash of pushed commits).

## 6. Conventions this repo enforces (learned from the runbook + the v81–v90 reports)

These are not style preferences; each one exists because it already cost someone a defect.

1. **Achromatic by law** — `grep 'rgb(\|#[0-9a-fA-F]\{3,6\}'` on new frontend files must be empty.
2. **No date traps** — no `getDay(` / `getHours(` / `toLocaleString(` in new files; formatting is
   centralised in `format.ts`, and the timezone falls back to `"UTC"` with a disclosure banner.
3. **Overlays portal to `document.body`** — `PageSection` carries `.rise`
   (`transform: translateY(8px)`), which creates a containing block and **clips `position: fixed`
   children**. This shipped as a real defect once.
4. **`StatusChip` returns `null` for unmapped keys** — so a mapping bug is an *invisible cell*, not
   an error. The runbook records this trap recurring twelve times.
5. **Frozen lint baseline** — the count is the gate (currently 9 warnings on `admin_dashboard`
   per the FEATURE_15 report; the older runbook baseline of 36 predates the prettier cleanup).
   Not fewer, not more, and prettier runs on touched files only.
6. **Zero new dependencies** — `git diff --stat -- package.json` must be empty.
7. **Zero direct browser requests to `:8108`** — all traffic proxies through the TanStack server.
8. **FastAPI literal-before-parameter** — `GET /customers` must be registered before
   `/customers/{id}/360`; same for `/sessions`. The runbook calls these "the highest-risk lines in
   the entire set".
9. **One cookbook = one revertable commit**; never squash.

## 7. Open questions / debt I could not close from the repo alone

Carried from `MASTER_APPLY_RUNBOOK.md` §8–§10, plus two drifts I found myself.

**Still awaiting a decision (runbook §8)**

1. H-1 retention floor — clamp to 30 days server-side? (blocks C10; recommendation was yes)
2. C-1 — run `SELECT count(*) FROM conversation.call_sessions WHERE max_frustration_score IS NULL;`
   (expected `0`; a non-zero answer changes C4 *and* C9's KPI math)
3. H-5 — UUID guard on `customer_360`, or accept 500s on malformed ids?
4. C14 §6.5 — may `superviseur` read the error/plan catalogs, or is `administrateur` correct?
5. **No user store in the backend** — admin auth is a single env-var credential pair
   (`ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_ROLE`). Real multi-user admin auth is a feature, not a
   config change. Raised by C10 §8.3 and C11 §0.3, still unanswered.
6. C9 §8.1 — `system_overview()` reports eleven services as `"online"` **hardcoded**. C9 strips the
   fabricated status rather than display a lie; real probes need an eleven-way `/health` fan-out.

**Modelled but still unexposed (runbook §9)** — `CustomerInteraction`, `Payment`, `PaymentPlan`,
`ConsentRecord`; `reference.geo_aliases` (deliberate); the automation engine `/rules` implied
(never built). Note `CallbackSchedule`'s lifecycle fields are **no longer** in this list —
FEATURE_15's read-only detail modal surfaced them, and §9 was amended in place.

**Verification debt (runbook §10)** — `formatPercent`'s 0–1 vs 0–100 contract; `persistence/base.py`
`SoftDelete` column name; `open_invoices.amount` actually being *total invoiced*, not outstanding
(FEATURE_21 addressed the labelling — worth confirming the two reports agree).

**Two drifts I found in this pass** (both documentation/default-value, neither a code bug):

- `commands.md` §"System Architecture & Ports" contradicts the source: it lists business-api on
  8100 (actually 8108), notification-service on 8108 (actually 8106) and agent-worker on 8106
  (it has no HTTP port). It also documents `apps/supervisor-dashboard`, which does not exist — the
  `Makefile` builds `Frontend/admin_dashboard` and `Frontend/customer_portal`.
- `apps/agent-worker/src/config/settings.py` defaults `business_api_url` to `localhost:8107`, which
  is **token-service**, and `nms_service_url` to `localhost:8108`, which is **business-api**. Both
  are correctly overridden in `docker-compose.apps.yml`, and `_distinct_service_urls()` does not
  fire because the two defaults differ from each other — so the risk is confined to host-dev runs
  that don't set these vars. `.env.example` already carries a corrective comment for
  `BUSINESS_API_URL`; `NMS_SERVICE_URL` is set to the container address `http://nms-sim:8108`,
  which will not resolve from the host (host mapping is `8110`).

## 8. Where to be careful

The `providers/` vendor boundary, the SAVEPOINT in `ExecutionService`, the advisory-lock append in
`PgAuditLedger`, the four verdict checks, the mock-money refusal, and the server-only token read in
`business-api.ts` are all load-bearing. Each is short enough to look harmless and expensive to
"simplify". If a change touches one of them, it deserves its own commit and its own note.

---

*No file in `apps/`, `services/`, `packages/`, `Frontend/` or `infra/` was modified by this pass.*
