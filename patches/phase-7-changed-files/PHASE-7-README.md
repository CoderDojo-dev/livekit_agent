# Phase 7 — Execution & Sensitive Actions (+ review patches)

**Goal:** real actions happen safely — every sensitive action is identity-gated, decisioned,
policy-verdicted, then **dispatched idempotently and audited**. No sensitive action without a verdict.

**Exit criterion (met):** payment (§5.2), deferral (§5.3), and SIM unblock (§5.5) complete end to
end with correct behaviour on happy / refusal / escalation paths; a retried action never
double-executes.

This drop also folds in four fixes from your review (notes 1, 5a, 5c, 6). The two larger items
(Postgres, GLPI lifecycle) are **sequenced**, not skipped — see the table below.

---

## 1. Your review — disposition

| # | Note | Verdict | Where |
|---|------|---------|-------|
| 1 | Split the combined `knowledge-glpi-mcp` | **Done now** | `mcp-servers/ai-knowledge-rag/` (knowledge), `mcp-servers/ticketing-glpi/` + `messaging-gateway/` scaffolds |
| 2 | GLPI `resolve_ticket` / lifecycle | **Phase 9** | `ticketing-glpi/README.md` lists the planned tools incl. resolve |
| 3 | Postgres migration, services via REST | **Phase 7.5 (Persistence)** | architecture already REST-correct; see §6 |
| 4 | CIN column in CRM schema | **Phase 7.5** | lands with the Postgres CRM schema |
| 5a | PII in worker logs | **Done now** | `observability/log_masking.py` + log `customer_id`, never name/MSISDN |
| 5b | Hardcoded localhost ports | **Already env-driven** | override values for Docker DNS in §4 |
| 5c | Standard error mapping service↔worker | **Done now** | `tools/outcomes.py` contract; tightened agent instructions |
| 6 | `ConsentTask` still empty | **Done now** | `tasks/consent_task.py` implemented + wired into Triage |

---

## 2. What changed

### New — Phase 7 Execution
- `services/execution-service/` — idempotent dispatch (CDC §4.7). `POST /execute` with an
  `idempotency_key`; a repeat key returns the original reference (`replay=true`) and does **not**
  re-execute. Every execution is written to its hash-chained ledger; `GET /audit/verify`. Port **8105**.
- `apps/agent-worker/src/clients/execution_client.py` — typed client; returns a standard outcome.
- `apps/agent-worker/src/tasks/payment_confirm_task.py` — `PaymentConfirmTask` (explicit amount
  confirmation before `EXECUTE_PAYMENT`, CDC §6.1).
- `apps/agent-worker/src/agents/technical_agent.py` — `TechnicalAgent` + `unblock_sim` (SIM write
  path, identity-gated + guarded, CDC §5.5/§6.3).
- `tools/guarded_action.py` — the `AUTHORIZED` branch now **executes idempotently** (new key per
  session+action) and returns the result.
- `agents/billing_agent.py` — `make_payment` (confirm → guard → execute); deferral now executes.
- `tools/routing_tools.py` — adds `route_to_technical`.

### New — review patches
- `tasks/consent_task.py` — real `ConsentTask`; Triage collects consent **first**, then greets.
- `observability/log_masking.py` + `packages/pii-shield` — PII masking filter on every log record.
- `tools/outcomes.py` — one outcome shape (`executed` / `refused` / `escalate` / `failed`) with a
  `message` the LLM renders in-language. No more generic "I encountered an error".
- `mcp-servers/ai-knowledge-rag/` — knowledge MCP server, decoupled from GLPI.

### Moved / renamed / deleted (apply these)
- **DELETE** `mcp-servers/knowledge-glpi-mcp/`  → replaced by `ai-knowledge-rag/` (+ `ticketing-glpi/`).
- **DELETE** `apps/agent-worker/src/mcp_clients/knowledge_glpi_toolset.py` → replaced by `knowledge_toolset.py`.
- **.env:** rename `KNOWLEDGE_GLPI_MCP_URL` → `KNOWLEDGE_MCP_URL` (same value `http://localhost:8201/mcp`).

---

## 3. Apply
Unzip at the repo root (overwrites changed files, adds new ones), then perform the two deletions
and the `.env` rename above.

```bash
# from repo root
unzip -o phase-7-changed-files.zip
rm -rf mcp-servers/knowledge-glpi-mcp
rm -f  apps/agent-worker/src/mcp_clients/knowledge_glpi_toolset.py
# edit apps/agent-worker/.env:  KNOWLEDGE_GLPI_MCP_URL=...  ->  KNOWLEDGE_MCP_URL=http://localhost:8201/mcp
```

---

## 4. Run (local)

```bash
# domain services
cd services/context-service   && uvicorn context_service.main:app   --port 8101
cd services/knowledge-service && uvicorn knowledge_service.main:app --port 8102
cd services/decision-service  && uvicorn decision_service.main:app  --port 8103
cd services/policy-service    && uvicorn policy_service.main:app    --port 8104
cd services/execution-service && pip install -e . && uvicorn execution_service.main:app --port 8105   # NEW
# knowledge MCP server (renamed)
cd mcp-servers/ai-knowledge-rag && pip install -e . && python -m ai_knowledge_rag.server   # :8201/mcp
# worker
cd apps/agent-worker && python -m server console        # set SESSION_CALLER_MSISDN in .env
```

### Docker DNS (review note 5b)
The URLs are env-driven, so in Docker Compose set them to the service DNS names — no code change:
```
CONTEXT_SERVICE_URL=http://context-service:8101
DECISION_SERVICE_URL=http://decision-service:8103
POLICY_SERVICE_URL=http://policy-service:8104
EXECUTION_SERVICE_URL=http://execution-service:8105
KNOWLEDGE_MCP_URL=http://ai-knowledge-rag:8201/mcp
```

---

## 5. Proving the exit criterion

Pick the caller with `SESSION_CALLER_MSISDN` (`+21620155320` Amine fr · `+21629744108` Yousra ar VIP ·
`+21652310977` Karim en).

- **Consent first (note 6):** at call start the agent asks to record the call **before** greeting.
- **Payment — happy path (§5.2):** *"I want to pay my bill, 42.500 dinars."* → identity → amount
  confirmation → `AUTHORIZED` → **executed**, agent reads the `PAY-…` reference.
- **Payment — refusal:** decline the confirmation → policy `PAY_NO_CONFIRMATION` → the agent
  explains plainly (no "error").
- **Deferral — three verdicts:** Amine → **executed** (`DEF-…`); Karim (age 88<180) → **refused**
  (`DEF_MIN_AGE`); Yousra (VIP) → **escalate** (`ESC_VIP`) → Manager.
- **SIM (§5.5):** route to technical → *"unblock my SIM"* → identity → guard → **executed** (`SIM-…`).
- **Idempotency:** the worker uses one key per session+action, so a retried dispatch returns the
  same reference and does not double-execute.
- **Audit:** `curl http://localhost:8104/audit/verify` and `curl http://localhost:8105/audit/verify`
  → `{"intact": true, ...}`.
- **PII logs (note 5a):** worker logs show `customer_id=TT-100021`, never the name; any stray
  phone/email/ID run is masked.

### Offline tests (no keys/network)
```bash
cd services/execution-service && PYTHONPATH="src:../../packages/audit-trail/src" python -m pytest -q tests/   # 3
cd services/policy-service    && PYTHONPATH="src:../../packages/audit-trail/src" python -m pytest -q tests/   # 10
cd services/decision-service  && PYTHONPATH=src python -m pytest -q tests/                                     # 3
cd services/context-service   && PYTHONPATH=src python -m pytest -q tests/                                     # 5
cd services/knowledge-service && PYTHONPATH=src python -m pytest -q tests/                                     # 3
```

---

## 6. Honest scope notes & what's next

- **Why Postgres is Phase 7.5, not now:** the worker already talks to services over REST and never
  imports `mock_directory` — so the boundary your note asks for already exists. `mock_directory` is
  only each service's *internal* data source, swappable for a Postgres repository behind the exact
  same REST API. Doing it as a focused **Phase 7.5 — Persistence** (Postgres container + per-service
  repositories + Alembic migrations + the **CIN column**, note 4) keeps it clean; bolting half a
  schema onto Execution would not.
- **Execution adapters are mock:** `executor.dispatch()` returns a reference; real Billing/OCS/NMS
  adapters replace it behind the same idempotency+audit wrapper.
- **`deferrals_this_year` is 0** until the deferral-history store lands (Phase 7.5).
- **Audit is per-service today;** a single centralized chain in Postgres is Phase 11.
- **Next:** Phase 7.5 (Persistence) → **Phase 8 — Sentiment & Escalation** (frustration detection
  feeding the `ESC_FRUSTRATION` rule, full §10.1 wiring, SIP transfer, callback scheduling).

**Traceability:** CDC §4.7 → execution-service; §5.2/§6.1 → `make_payment` + `PaymentConfirmTask`;
§5.3 → deferral; §5.5/§6.3 → `unblock_sim`; §8.1 → `ConsentTask`; §14 → PII log masking; ADR §5.4 → MCP split.
