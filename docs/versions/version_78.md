# Version 78 — knowledge_search failsafe contract + GLPI Cloud migration + Frontend admin dashboard & customer portal

> **Base branch:** `version_77`
> **Files changed:** 1 modified (`.env.example`), ~500 added (`Frontend/`, `docs/versions/version_78.md`, plus `mcp-servers/ai-knowledge-rag/.../knowledge_search.py` from v77)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Dependency change:** none (Python); new Node/bun workspace for the two Lovable frontend apps (not yet wired into compose)

---

## Containers & SDK

| Item               | Change |
|---|---|
| New containers     | None — the two frontend apps ship source-only (no compose service, no container in infra/docker-compose yet) |
| livekit-agents SDK | `1.6.5` (unchanged) |
| livekit-server     | `v1.8.4` self-hosted profile unchanged |
| Docker Compose     | Unchanged (21 services) |
| Agent-worker image | Rebuilt locally for v77 PolicyClient (pushed in v77, unchanged here) |

---

## What's New in This Branch

### 1. `knowledge_search` failsafe (v77 patch, included via `a6bae0a` — first push)
`mcp-servers/ai-knowledge-rag/src/ai_knowledge_rag/tools/knowledge_search.py` — the tool contract changes from `list[dict]` to `dict` with an explicit status, permanently eliminating the only `ToolError` path of the knowledge layer.

**Before**: returning `[]` for an out-of-corpus query made FastMCP emit zero content blocks → livekit-agents 1.6.5's `_default_tool_result_resolver` raised `ToolError("Tool 'knowledge_search' completed without producing a result.")` (LiveKit reads only `result.content`, ignoring `structuredContent`). The call failed, the caller heard silence and hung up.

**After**: the tool always returns a status-carrying dict with at least 2 keys (always at least one text block, so always speakable for the LLM):
- `{"status": "ok", "passages": [...]}` — relevant passages found
- `{"status": "no_match", "passages": [], "detail": ...}` — nothing relevant (replaces the empty list; the agent now says "I don't have that information" instead of the whole tool call succeeding with nothing)
- `{"status": "unavailable", "passages": [], "detail": ...}` — the knowledge service could not answer (503, timeout, network); never silently empty

Proof (measured in report, red→green):
- Red proof executed **before** the patch (stage 0): out-of-corpus question `recette de couscous aux legumes ...` → service returned HTTP 200 `{"passages":[]}` (healthy), and running the worker path in the `agent-worker` container reproduced the ToolError 100% of the time.
- After the patch: the same journey returns `{"status":"no_match","passages":[]}` — the call succeeds, and the LLM produces a spoken "I don't have that information".
- The 503/timeout case returns `{"status":"unavailable","passages":[]}` logged loudly — failures stay in the logs, not on the call.
- Full chain: **125/125 PASS** on committed `a6bae0a` (`test_committed.ps1 -Ref HEAD`).

### 2. GLPI Cloud migration (`glpi-cloud-credentials-migration-results.md`, local)
The cloud instance was migrated from the old GLPI 10 `voiceagentai.fr33.glpi-network.cloud` (account ended/expired) to a new **GLPI 11** instance `voice-agent-ai.fr36.glpi-network.cloud`.

Verified migration (100% local, no push, results in the report above):
- **3 customers** recreated in GLPI 11 (login = `national_id`), `crm.customers.glpi_user_id` remapped: Amine Ben Salah → 7, Yousra Trabelsi → 8, Karim Gharbi → 9 (new ids).
- **20/20 tickets** recreated in the new instance, `ticketing.tickets.glpi_ticket_id` remapped sequentially.
- **Bidirectional consistency**: `mirror 20 == remote 20`, `only_remote: []`, `only_mirror: []` → CONSISTENT (nothing saved locally that does not exist in remote, and vice versa).
- Full live MCP CRUD test (create → status → update → resolve → close → lookup → delete) executed against the new instance via the worker's `ticketing-glpi` MCP client, test ticket purged. `initSession` → 200 both from the host and from the container.
- Tests: **177 passed, 9 skipped** (2 pre-existing collection errors out of scope).

The only file under version control touched by the migration is `.env.example`, which documents the new endpoint; the real tokens/`.env` stays git-ignored.

### 3. New Frontend workspace (`Frontend/`) — admin dashboard + customer portal
Two Lovable-generated React applications added under `Frontend/`:

| App | Stack | Purpose |
|---|---|---|
| `Frontend/admin_dashboard` | React 19 + Vite 8 + TypeScript + TanStack (Router/Start/Query) + Tailwind 4 + shadcn/ui (radix) + zod + recharts + cmdk + sonner + vaul + bun | Admin dashboard: advisor callbacks, escalation console, call monitoring, outage map, settings |
| `Frontend/customer_portal` | Same identical scaffold/dependencies + `portal/` app (native `orb`/`fixtures` components) | Customer-facing portal (tickets, claims, subscription, configuration) |

Both are `Lovable`-connected projects (see each `Frontend/*/AGENTS.md` — no history rewriting rules from Lovable apply here because we only add, never force-push).

Notes:
- No compose service yet: these are source-only apps, deployable/targetable via `bun dev` (server runs on Vite/Nitro with Tailwind CSS 4 through `@tailwindcss/vite`). There is **no `node_modules`** committed.
- Both apps carry identical RADIX dependency sets (scaffolded from the same Lovable template); `admin_dashboard` additionally has `src/server.ts`, `router.tsx`, `routeTree.gen.ts` (TanStack Start SSR), and its own `eslint.config.js`/`bunfig.toml`.
- `bun.lock` files are committed (lockfiles are not gitignored) so future `bun install` is reproducible.

### 4. `.env.example` — new cloud GLPI endpoint
```diff
-#GLPI_BASE_URL=https://voiceagentai.fr33.glpi-network.cloud/api.php/v1 #old api glpi endpoint
+#GLPI_BASE_URL=https://voice-agent-ai.fr36.glpi-network.cloud/apirest.php #new glpi instance (2026-08)
```

---

## Validation (pre-commit)

- Full validation chain (`scripts/test_committed.ps1 -Ref version_77`): **125/125 PASS** (24 + 74 + 10 + 17) on the committed v77 tree before adding these changes.
- knowledge_search fix: measured red→green in the agent-worker container (see v77 report for the exact reproduction journey).
- GLPI migration: `177 passed, 9 skipped`, bidirectional mirror/remote consistency checked.

---

## Out of Scope (left open, unchanged)

- No compose service for `Frontend/*` yet — deployment & reverse-proxy wiring is out of this version.
- No `.env` committed (tokens stay local, `.env.example` only documents).
- The real-traffic §7 control (requires a real call day for escalations counter).
- All items previously listed in v77 (identity verification timings, Twilio SIP, pre-existing ruff findings, etc.).
