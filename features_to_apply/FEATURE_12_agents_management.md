# Cookbook 12 — Agents Management (Persona Graph)

> **Branch of record:** `version_79` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`
> **Applies onto:** local `version_80`
> **Scope of this cookbook:** `Frontend/admin_dashboard/` + **one** additive read-only backend endpoint
> **Status:** design complete, not applied
> **Depends on:** Feature 0 (substrate), Feature 9 (`delta` optional on `StatCard`/`HeroStat`), Feature 1 (`Modal` portal fix, `Segmented type="button"`)

---

## §0 — BLOCKING DECISIONS (read before writing a line of code)

This is the last named feature from your original Phase-3 list: *"Agents management (customer agent, technical agent, etc.)"*. It is also the feature whose extraction most changed what can honestly be built. Three findings are blocking and need your sign-off, because two of them contradict the plain reading of the request.

### §0.1 — "Agents management" cannot mean management. It can only mean observation.

The five agents are **Python classes**, not rows.

```
apps/agent-worker/src/agents/
  __init__.py                 76 B
  base_agent.py            9 060 B   BaseTelecomAgent
  triage_agent.py          5 360 B   TriageAgent
  account_services_agent.py 3 878 B  AccountServicesAgent
  billing_agent.py         6 829 B   BillingAgent
  technical_agent.py       7 600 B   TechnicalAgent
  manager_agent.py         6 345 B   ManagerAgent
  domains.py               3 617 B   DOMAINS registry
  instruction_kit.py      12 581 B   instruction layers + contract enforcement
```

There is **no agents table** in `packages/persistence/src/persistence/models/` — the eleven model modules were read exhaustively across Phases 1–3 and none defines an agent, persona, or prompt entity. There is **no configuration record**. A persona's identity, its prose, its tool set and its language lock are all expressed in source code and frozen at import time.

Therefore:

- **Creating an agent** = writing a new Python module. New business logic → **Constraint 3 forbids it.**
- **Editing a persona's instructions** = editing `core_instructions` in a `.py` file and redeploying the worker. Not a runtime write path; no endpoint could exist without inventing one.
- **Enabling/disabling an agent** = deleting a `route_*` tool from a tool set, which by design mutates the generated mandate (see §2.4). There is no flag to flip.

**Decision:** `/agents` ships **read-only**. It presents the persona graph as it exists in the deployed code, plus the one genuinely observable runtime dataset (§0.2). **No create, no edit, no enable/disable, no prompt editor.** Shipping any of those controls — even disabled — would assert a capability the system does not have. This follows the Feature 5 precedent (*remove, don't disable*) and the Cookbook 7 precedent (guardrail modification structurally forbidden, page ships read-only).

> **CONFIRM:** if by "agents management" you meant *editing personas from the dashboard*, that is a **new backend subsystem** (persona storage, versioning, hot-reload into a running LiveKit worker, and a safety-review path for prompt changes that govern a live phone line). It is a project, not a cookbook. Say the word and I will scope it as its own proposal — but I will not smuggle it in here.

### §0.2 — There is exactly one real agent dataset, and it is `conversation.turns.active_agent`.

From `base_agent.py`, in `on_user_turn_completed`:

```python
writer.record_turn(
    speaker="caller", text=transcript,
    active_agent=type(self).__name__, language=getattr(user_data, "language", None),
)
```

`Turn.active_agent` (confirmed on the model in `conversation.py`) stores **`type(self).__name__`** — the raw Python class name: `"TriageAgent"`, `"BillingAgent"`, `"AccountServicesAgent"`, `"TechnicalAgent"`, `"ManagerAgent"`.

This is the whole of the agents' runtime footprint, and it is real, durable and queryable. It is what makes this page worth building: **which personas actually handle traffic, how the handoff graph behaves in production, and whether any persona is dead code.**

### §0.3 — The page mirrors source code, so the mirror can drift. Make drift visible, never silent.

The static roster (names, domains, tool sets) has to be transcribed into the frontend, because no endpoint serves it. That transcription is a **duplicate of a source of truth**, which is exactly the failure mode `domains.py` was written to prevent:

> *"so a domain can never again be half-wired -- named in a prompt but missing from a tool set, or vice versa."*

If someone adds a sixth persona, a hardcoded frontend list would silently omit it — the page would confidently show five agents and be wrong.

**Decision:** the activity endpoint is the **authority on existence**. The UI renders the union of (static catalog) ∪ (class names observed in the database). Any observed class name absent from the catalog renders as an explicit **"Unrecognized persona"** row rather than being dropped. Drift becomes a visible defect on screen instead of an invisible omission. This is the single most important design property of the page.

---

## §1 — Feature name & scope

**Feature 12 — Agents Management (Persona Graph).**

In scope:

- New route `/agents` (Nexus admin dashboard).
- Read-only roster of the five personas: display name, role in the graph, owned domain, routing capability, tool set, language lock, terminal-escalation flag.
- Real runtime activity per persona over a selectable window: attributed turns, distinct sessions, last observed.
- Persona detail panel (Modal) with the full derived instruction layer stack and tool inventory.
- Explicit surfacing of the three domains from `domains.py` and their deterministic transition lines in `fr` / `ar` / `en`.
- One additive backend read endpoint.

Out of scope (with reasons):

- Any persona mutation (§0.1).
- The client/customer dashboard (Phase-3 constraint).
- Live worker health / process supervision — `AgentServer` exposes no HTTP surface (§2.1); this belongs to Cookbook 9 §8.1 (real service health probes), still awaiting approval.
- Per-call agent timeline — that is Feature 4's session detail (`turns[].agent` is already rendered there).

---

## §2 — Backend reference (exact names and paths)

### §2.1 — `apps/agent-worker/src/server.py` (`b03539f62174c0012ab772b9fc32b1de9f026da2`)

**Correction to an assumption I made out loud during extraction:** the presence of `server.py` looked like an HTTP surface. It is not one.

```python
server = AgentServer(num_idle_processes=1, job_memory_warn_mb=768)

@server.rtc_session(agent_name=settings.livekit_agent_name.strip())
async def entrypoint(ctx: JobContext) -> None: ...

if __name__ == "__main__":
    agents.cli.run_app(server)
```

`AgentServer` is the LiveKit **worker job server**. `@server.rtc_session` registers a room-session entrypoint. There is no route decorator, no FastAPI app, no port binding of our own. **The agent worker cannot be queried over HTTP.** Anything the dashboard shows about agents must come from the database or from static transcription.

Also established here — the composition root always starts **`TriageAgent`**:

```python
await session.start(agent=TriageAgent(language=language), room=ctx.room)
```

Triage is the **sole entry persona**; every call begins there. That is a structural fact worth showing on the page.

### §2.2 — `apps/agent-worker/src/agents/domains.py` (`10b8c6e4f2f7a7899212116fd45e951b15f9ed72`)

Module docstring:

> *"Single source of truth for the specialist domains of the persona graph. A domain is declared ONCE here: the topics that belong to it, the tool that hands a caller over to it, and the deterministic spoken transition line. Both the routing mandate (agents.instruction_kit) and the handoff tools (tools.routing_tools) read from this table…"*

```python
@dataclass(frozen=True, slots=True)
class Domain:
    key: str
    route_condition: str
    own_topics: str
    route_tool: str
    lines: Mapping[str, str]
```

`DOMAINS` contains **exactly three** entries:

| key | `route_tool` | owns |
|---|---|---|
| `billing` | `route_to_billing` | Balance, invoice, payment and deferral requests |
| `account` | `route_to_account_services` | Plan, recharge, roaming and phone-line requests |
| `technical` | `route_to_technical` | SIM, network and connectivity problems |

Derived exports: `DOMAIN_BY_KEY`, `DOMAIN_BY_ROUTE_TOOL`, `ROUTE_TOOL_NAMES`, `SUPPORTED_LANGUAGES = frozenset({"fr","ar","en"})`.

**Trap — three domains, five agents.** `TriageAgent` and `ManagerAgent` are personas with **no domain**. Rendering `DOMAINS` as if it were the agent roster would show three agents and lose two. The roster and the domain table are different objects and are rendered as different sections.

Deterministic transition lines are held per language, e.g. `billing`/`fr`: *"Très bien, je vous mets en relation avec notre service de facturation."* These are real product copy and are worth surfacing — they are what the caller actually hears at a handoff.

### §2.3 — `apps/agent-worker/src/agents/base_agent.py` (`839146b2cf5bdcc5d84c3ab9f5bbcdb2b9ceeec9`)

`BaseTelecomAgent(Agent)` — every persona inherits it.

Construction contract:

- `core_instructions` (persona prose) **xor** `instructions` (pre-assembled); passing both raises `ValueError`.
- `end_conversation` and `switch_spoken_language` are **auto-appended** to every persona's tool set.
- `capabilities` declares tool names not introspectable from tool objects (MCP toolsets), e.g. `{"knowledge_search"}`.
- `available = tool_names(merged_tools, extra=capabilities)`.
- `enforce_contract(type(self).__name__, instructions, available)` runs at construction.
- `self._capabilities` and `self._available_tool_names` are explicitly *"Exposed for tests and runtime diagnostics; not used by the SDK."*
- `_LANG_MAP = {"fr": "French", "ar": "Arabic", "en": "English"}`, defaulting to `fr` on an unknown code.

`NO_DEAD_END_MANDATE` is marked **DEPRECATED (v64)**, as is `merge_instructions`. Both are retained only for historical check scripts. **They must not be presented on the page as live behaviour** — doing so would document a mandate that no current persona receives.

`on_user_turn_completed` is where `active_agent` is written (§0.2), and also where the frustration de-escalation note is injected when `decide(user_data) == "frustration"`.

### §2.4 — `apps/agent-worker/src/agents/instruction_kit.py` (`2933985d995cdaf3aaeefad90b4672139c1af68a`)

The conceptual heart of the feature. Docstring:

> *"The routing mandate used to be a frozen block injected into every persona, so it could order BillingAgent to call route_to_billing -- a tool BillingAgent does not have. Here the mandate is a PROJECTION of the registered tool set: an instruction citing an unavailable tool is not merely discouraged, it is unrepresentable."*

**Instruction layer order** (`build_persona_instructions`):

```
core  [+ KNOWLEDGE_ABSTENTION_RULE if knowledge_search available]
  + routing_mandate(available)
  + CLOSING_PROTOCOL
  + LANGUAGE_SWITCH_POLICY
  [+ TTS_LANGUAGE_REMINDER if tts_provided]
```

**`routing_mandate(available)` — derived, not declared.** For each domain: if the persona owns `route_tool` → a routing line; else → an explicit *ownership* line. Absence produces ownership. This is why the page can state, truthfully and without a database, which persona owns which domain: **it is a function of the tool set.**

**Terminal escalation is derived too:**

```python
terminal = ESCALATION_TOOL not in available   # "escalate_to_manager"
```

A persona lacking `escalate_to_manager` **is** the manager: it claims no domain and is pointed at `transfer_to_human`. `ManagerAgent`'s terminal status is therefore an emergent property, not a field. The page shows it as **derived**, and says so.

**`KNOWN_TOOL_VOCABULARY`** — 38 tool names in seven groups (routing/flow, billing, account services, technical, identity, ticketing). `scripts/persona_contract_checks.py` asserts the catalog covers every `@function_tool` in the tree, *"which turns a forgotten entry into a CI failure instead of a silent validation gap."*

**`enforce_contract` — the finding that matters operationally:**

```python
STRICT_ENV_VAR = "STRICT_PERSONA_CONTRACT"

def enforce_contract(persona, instructions, available) -> None:
    violations = instruction_violations(instructions, available)
    if not violations:
        return
    detail = f"{persona} is instructed to use unavailable tools: {violations}"
    if os.getenv(STRICT_ENV_VAR) == "1":
        raise RuntimeError(detail)
    logger.error("persona contract violation - %s", detail)
```

Phase 1 established that **`STRICT_PERSONA_CONTRACT` is never set anywhere** — not in `.env.example`, not in compose, not in CI. So in every environment you actually run, a persona contract violation is a `logger.error` line and **nothing else**. It does not surface in the database, in the audit ledger, or on any endpoint. See §8.2.

### §2.5 — `packages/persistence/src/persistence/models/conversation.py` (`ec4592ad`)

`Turn`: `session_id` FK, `turn_index`, `speaker` (`caller|agent`), `transcript_masked`, **`active_agent`**, `language`, `UniqueConstraint(session_id, turn_index, speaker)`.

`CallSession`: `channel` (`voice|chat`), `final_disposition` (`resolved|escalated|dropped|abandoned`), `max_frustration_score Numeric(5,2)` **nullable**, `start_time`, `duration_seconds`, `audio_record_url`.

**MUST-VERIFY (V1):** whether `Turn` carries a `created_at` (i.e. the `Timestamps` mixin). It was not confirmed during extraction. **The query in §3.2 deliberately does not depend on it** — it windows on `CallSession.start_time`, which is confirmed. Do not "simplify" it to `Turn.created_at` without checking.

**MUST-VERIFY (V2):** `base_agent.py` records `active_agent` on **`speaker="caller"`** turns. Whether `conversation/writer.py` also stamps `active_agent` on `speaker="agent"` turns was not read. This decides whether "turns" means caller turns, agent turns, or both. Until confirmed, the column is labelled **"Attributed turns"** — never "Turns handled" or "Replies" — and §8.1 tracks it.

### §2.6 — `apps/business-api/src/business_api/main.py` (`ff52daff`)

All 34 routes captured verbatim three times. **No route mentions agents, personas, prompts or instructions.** The nearest neighbours are `/api/v1/sessions/{session_id}` (returns `turns[].agent`) and `/api/v1/telemetry/timeline`.

---

## §3 — Endpoints

### §3.1 — Existing, reused

| Method | Path | Role | Use here |
|---|---|---|---|
| `GET` | `/api/v1/system/overview` | `superviseur` | `metrics.total_calls`, `metrics.total_turns` for the hero denominators. Already wrapped by Feature 9's `getSystemOverview`. |

Nothing else existing is usable. That is the whole problem.

### §3.2 — New: `agent_activity` in `repositories.py`

**Justification (identical in kind to C4 `session_list`, C8 `decision_ledger`, C9 `analytics_trend`, C10 `audit_entries`, C11 `customer_list`):** this is a read-only aggregate over an existing column of an existing table. It creates **access**, not behaviour. No model changes, no writes, no new business rules.

Add to `SupervisionRepository` in `apps/business-api/src/business_api/repositories.py`.

> `repositories.py` does **not** import `os`, `datetime` or `timedelta`. C9/C10/C11 each add `import os`. Add only what is missing; do not duplicate an import another cookbook already added.

```python
# --- imports to ensure present at the top of repositories.py ---
# from datetime import datetime, timedelta, timezone
# from sqlalchemy import func

    def agent_activity(self, days: int = 30) -> dict:
        """Per-persona activity aggregated from conversation.turns.active_agent.

        Read-only. Windows on CallSession.start_time (confirmed present) rather
        than Turn.created_at (unverified), joining turns to their session.
        """
        window_days = max(1, min(int(days or 30), 365))
        since = datetime.now(timezone.utc) - timedelta(days=window_days)

        rows = (
            self.session.query(
                Turn.active_agent.label("agent"),
                func.count(Turn.id).label("turn_count"),
                func.count(func.distinct(Turn.session_id)).label("session_count"),
                func.max(CallSession.start_time).label("last_seen"),
            )
            .join(CallSession, CallSession.id == Turn.session_id)
            .filter(CallSession.start_time >= since)
            .filter(Turn.active_agent.isnot(None))
            .filter(Turn.active_agent != "")
            .group_by(Turn.active_agent)
            .order_by(func.count(Turn.id).desc())
            .all()
        )

        agents = [
            {
                "agent": row.agent,
                "turns": int(row.turn_count or 0),
                "sessions": int(row.session_count or 0),
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        ]
        return {
            "window_days": window_days,
            "total_turns": sum(a["turns"] for a in agents),
            "total_sessions": sum(a["sessions"] for a in agents),
            "agents": agents,
        }
```

Notes on the shape:

- `int(... or 0)` mirrors the defensive style already used in `kpis()`; it also avoids the class of bug that produced the live `max_frustration` 500 (`float(None)`).
- `last_seen` is `.isoformat()`d server-side, matching the C10 `audit_entries` convention.
- `total_sessions` is a **sum of per-agent distinct counts**, so a session touched by three personas counts three times. That is intentional — it is the denominator for "share of attributed sessions", not a session census. It is labelled accordingly in the UI and called out in §8.4.
- `days` is clamped **1–365** server-side. Never trust the client (C9 clamps 1–90, C10 clamps limit 1–200).

### §3.3 — New route in `main.py`

Place it **immediately after `/api/v1/telemetry/timeline`** and before `/api/v1/audit/verify`, keeping the supervision block contiguous.

```python
@app.get("/api/v1/agents/activity")
def agent_activity(session: DbSession, role: SuperviseurRole, days: int = 30) -> dict:
    """Per-persona activity aggregated from conversation turns."""
    return SupervisionRepository(session).agent_activity(days)
```

**Role:** `SuperviseurRole`, matching `/kpis`, `/system/overview` and `/telemetry/timeline`. This is aggregate operational telemetry with **no PII** — it returns class names and counts only. It does not warrant `administrateur`, and `conseiller` has no reason to see platform-wide persona statistics.

**Path safety:** `/api/v1/agents/activity` has a literal second segment and cannot collide with any `{id}` pattern — unlike the `/advisors/coverage` and `/customers` hazards, no ordering precaution is required. There is no `/api/v1/agents/{id}` route and none is proposed.

### §3.4 — CORS / middleware

**No change.** `GET` is already in `allow_methods`, and all traffic goes through the TanStack server proxy chosen in Feature 0, so the browser never touches `:8108` directly.

---

## §4 — Authoritative contract table

This table is the contract. Where it disagrees with prose elsewhere, this table wins.

| Field | Type | Source | Notes |
|---|---|---|---|
| `window_days` | `number` | echo of clamped input | 1–365 |
| `total_turns` | `number` | sum | denominator for turn share |
| `total_sessions` | `number` | sum of per-agent distincts | **over-counts by design** (§8.4) |
| `agents[].agent` | `string` | `Turn.active_agent` | **raw Python class name** |
| `agents[].turns` | `number` | `count(Turn.id)` | see V2 — "attributed", not "handled" |
| `agents[].sessions` | `number` | `count(distinct Turn.session_id)` | |
| `agents[].last_seen` | `string \| null` | `max(CallSession.start_time)` ISO | null only if all sessions lack `start_time` |

---

## §5 — Frontend implementation plan

### §5.1 — Files

**New**

| Path | Purpose |
|---|---|
| `src/lib/api/agents.server.ts` | typed server fn wrapping the new endpoint |
| `src/lib/nexus/agent-catalog.ts` | the static persona catalog transcribed from source |
| `src/lib/nexus/agent-view.ts` | pure mappers/formatters |
| `src/components/nexus/agent-detail.tsx` | Modal detail panel |
| `src/routes/agents.tsx` | the page |

**Modified**

| Path | Change |
|---|---|
| `src/lib/api/query-keys.ts` | `+ agentKeys` |
| `src/lib/nexus/nav.ts` | `+ /agents` under **INSIGHTS**, shortcut `G G` |
| `src/routeTree.gen.ts` | regenerated by the dev server (do not hand-edit) |

**Not touched:** `status.ts` (twelfth consecutive cookbook), `styles.css`, `primitives.tsx`, `blocks.tsx`, `format.ts`, `data.ts` (this route has **no mock to delete** — `/agents` does not exist in the template).

### §5.2 — `src/lib/api/agents.server.ts`

```ts
import { createServerFn } from "@tanstack/react-start"
import { z } from "zod"

import { businessApi } from "@/lib/api/business-api"
import { authedMiddleware, inputValidator, requireRole } from "@/lib/api/middleware"

export type AgentActivityRow = {
	agent: string
	turns: number
	sessions: number
	last_seen: string | null
}

export type AgentActivity = {
	window_days: number
	total_turns: number
	total_sessions: number
	agents: AgentActivityRow[]
}

const activityInput = z.object({
	days: z.number().int().min(1).max(365).default(30),
})

export const getAgentActivity = createServerFn({ method: "GET" })
	.middleware([authedMiddleware, requireRole("superviseur")])
	.inputValidator(inputValidator(activityInput))
	.handler(async ({ data }) =>
		businessApi<AgentActivity>("/api/v1/agents/activity", {
			method: "GET",
			query: { days: String(data.days) },
		}),
	)
```

`requireRole` is a **factory** — `requireRole("superviseur")`, not `requireRole` (Feature 2 correction #1). `GET` transport is correct here: this is a read, so the React Start CSRF constraint that forced `POST` in C2/C10 does not apply.

### §5.3 — `src/lib/nexus/agent-catalog.ts`

Transcribed from source. Every entry cites the file it came from so the next reader can re-verify rather than trust.

```ts
/**
 * Static persona catalog, transcribed from the agent-worker source at
 * version_79 (eda5f58). There is no endpoint for this data: personas are
 * Python classes, not rows (Cookbook 12 §0.1).
 *
 * `className` MUST match `type(self).__name__`, which is what
 * conversation.turns.active_agent stores (base_agent.py).
 *
 * If a persona is added or renamed in apps/agent-worker/src/agents/, this file
 * goes stale. Drift is surfaced at runtime, not hidden: any class name observed
 * in the database but missing here renders as an "Unrecognized persona" row.
 */

export type AgentDomainKey = "billing" | "account" | "technical"

export type AgentCatalogEntry = {
	className: string
	label: string
	role: string
	/** Domain owned by this persona, or null for Triage/Manager. */
	owns: AgentDomainKey | null
	/** Domains this persona can route away. */
	routes: AgentDomainKey[]
	/** True when escalate_to_manager is absent -> derived terminal point. */
	terminal: boolean
	/** True when this persona starts every call (server.py). */
	entryPoint: boolean
	source: string
}

export const AGENT_CATALOG: AgentCatalogEntry[] = [
	{
		className: "TriageAgent",
		label: "Triage",
		role: "Entry persona. Starts every call and routes to a specialist.",
		owns: null,
		routes: ["billing", "account", "technical"],
		terminal: false,
		entryPoint: true,
		source: "agents/triage_agent.py",
	},
	{
		className: "BillingAgent",
		label: "Billing",
		role: "Balance, invoice, payment and deferral requests.",
		owns: "billing",
		routes: [],
		terminal: false,
		entryPoint: false,
		source: "agents/billing_agent.py",
	},
	{
		className: "AccountServicesAgent",
		label: "Account Services",
		role: "Plan, recharge, roaming and phone-line requests.",
		owns: "account",
		routes: [],
		terminal: false,
		entryPoint: false,
		source: "agents/account_services_agent.py",
	},
	{
		className: "TechnicalAgent",
		label: "Technical",
		role: "SIM, network and connectivity problems.",
		owns: "technical",
		routes: [],
		terminal: false,
		entryPoint: false,
		source: "agents/technical_agent.py",
	},
	{
		className: "ManagerAgent",
		label: "Manager",
		role: "Final escalation point. Claims no domain; uses transfer_to_human.",
		owns: null,
		routes: [],
		terminal: true,
		entryPoint: false,
		source: "agents/manager_agent.py",
	},
]

/** Transcribed verbatim from agents/domains.py (DOMAINS). */
export type DomainCatalogEntry = {
	key: AgentDomainKey
	ownTopics: string
	routeTool: string
	lines: { fr: string; ar: string; en: string }
}

export const DOMAIN_CATALOG: DomainCatalogEntry[] = [
	{
		key: "billing",
		ownTopics: "Balance, invoice, payment and deferral requests",
		routeTool: "route_to_billing",
		lines: {
			fr: "Très bien, je vous mets en relation avec notre service de facturation.",
			ar: "حسنًا، سأحوّلك إلى قسم الفوترة لدينا.",
			en: "Sure, I'm connecting you with our billing department.",
		},
	},
	{
		key: "account",
		ownTopics: "Plan, recharge, roaming and phone-line requests",
		routeTool: "route_to_account_services",
		lines: {
			fr: "Très bien, je vous mets en relation avec notre service de gestion de compte.",
			ar: "حسنًا، سأحوّلك إلى قسم إدارة الحساب لدينا.",
			en: "Sure, I'm connecting you with our account services team.",
		},
	},
	{
		key: "technical",
		ownTopics: "SIM, network and connectivity problems",
		routeTool: "route_to_technical",
		lines: {
			fr: "Très bien, je vous mets en relation avec notre service technique.",
			ar: "حسنًا، سأحوّلك إلى الدعم الفني لدينا.",
			en: "Sure, I'm connecting you with our technical support.",
		},
	},
]

/** Shared instruction layers every persona receives (instruction_kit.py). */
export const INSTRUCTION_LAYERS = [
	{
		name: "Persona core",
		detail: "Hand-written domain prose, unique to each persona.",
		conditional: null as string | null,
	},
	{
		name: "Knowledge abstention rule",
		detail:
			"Ground answers strictly in retrieved passages; speak them, never read them aloud verbatim.",
		conditional: "only when knowledge_search is available",
	},
	{
		name: "Routing mandate",
		detail:
			"Projected from the registered tool set. A persona that cannot route a domain away is told it owns it.",
		conditional: null,
	},
	{
		name: "Closing protocol",
		detail:
			"Confirm nothing else is needed, then call end_conversation; the tool delivers the farewell.",
		conditional: null,
	},
	{
		name: "Language switch policy",
		detail:
			"Never drift; switch only on an explicit caller request via switch_spoken_language.",
		conditional: null,
	},
	{
		name: "TTS language lock",
		detail: "Speak only the configured language.",
		conditional: "only when a TTS provider is configured",
	},
]

export const AGENT_LANGUAGES = ["fr", "ar", "en"] as const
```

> **Deliberate omission.** `NO_DEAD_END_MANDATE` and `merge_instructions` are **DEPRECATED (v64)** and are not in this catalog. Documenting them on screen would describe a mandate no live persona receives (§2.3).

### §5.4 — `src/lib/nexus/agent-view.ts`

```ts
import type { AgentActivityRow } from "@/lib/api/agents.server"
import { AGENT_CATALOG, type AgentCatalogEntry } from "@/lib/nexus/agent-catalog"

export type AgentRow = {
	className: string
	label: string
	catalog: AgentCatalogEntry | null
	turns: number
	sessions: number
	lastSeen: string | null
	turnShare: number
}

const BY_CLASS = new Map(AGENT_CATALOG.map((entry) => [entry.className, entry]))

/**
 * Split a Python class name into words: "AccountServicesAgent" -> "Account Services".
 * Used ONLY for class names absent from the catalog, so drift is legible
 * rather than raw (Cookbook 12 §0.3).
 */
export function humanizeClassName(className: string): string {
	const withoutSuffix = className.replace(/Agent$/, "")
	const spaced = withoutSuffix.replace(/([a-z0-9])([A-Z])/g, "$1 $2").trim()
	return spaced || className
}

export function agentLabel(className: string): string {
	return BY_CLASS.get(className)?.label ?? humanizeClassName(className)
}

export function isKnownAgent(className: string): boolean {
	return BY_CLASS.has(className)
}

/** Union of the static catalog and everything actually observed. */
export function mergeAgentRows(
	observed: AgentActivityRow[],
	totalTurns: number,
): AgentRow[] {
	const byClass = new Map<string, AgentActivityRow>()
	for (const row of observed) byClass.set(row.agent, row)

	const seen = new Set<string>()
	const rows: AgentRow[] = []

	for (const entry of AGENT_CATALOG) {
		const hit = byClass.get(entry.className)
		seen.add(entry.className)
		rows.push({
			className: entry.className,
			label: entry.label,
			catalog: entry,
			turns: hit?.turns ?? 0,
			sessions: hit?.sessions ?? 0,
			lastSeen: hit?.last_seen ?? null,
			turnShare: totalTurns > 0 ? (hit?.turns ?? 0) / totalTurns : 0,
		})
	}

	for (const row of observed) {
		if (seen.has(row.agent)) continue
		rows.push({
			className: row.agent,
			label: humanizeClassName(row.agent),
			catalog: null,
			turns: row.turns,
			sessions: row.sessions,
			lastSeen: row.last_seen,
			turnShare: totalTurns > 0 ? row.turns / totalTurns : 0,
		})
	}

	return rows.sort((a, b) => b.turns - a.turns)
}

/**
 * Absolute instant, no relative-time arithmetic and no locale weekday lookup.
 * Cookbook 3/8/9 rule: never getDay()/getHours() on a backend instant.
 */
export function formatLastSeen(iso: string | null): string {
	if (!iso) return "—"
	const datePart = iso.slice(0, 10)
	const timePart = iso.slice(11, 16)
	return timePart ? `${datePart} ${timePart}` : datePart
}

export function sharePercent(share: number): string {
	if (!Number.isFinite(share) || share <= 0) return "0%"
	const pct = share * 100
	return pct < 1 ? "<1%" : `${Math.round(pct)}%`
}

export function routesLabel(entry: AgentCatalogEntry | null): string {
	if (!entry) return "Unknown"
	if (entry.terminal) return "Terminal"
	if (entry.routes.length === 0) return "Specialist"
	return `Routes ${entry.routes.length}`
}
```

**Why `formatLastSeen` slices the string.** Cookbooks 3, 8 and 9 all established that constructing a `Date` from a backend instant and reading `getDay()`/`getHours()` silently re-interprets it in the browser's timezone. Operators here are in `Africa/Tunis`; a viewer elsewhere would see a different day for the same event. String slicing preserves the server's own rendering. **The date-trap grep in §6 must return zero hits in this file.**

### §5.5 — Status chips: the trap, tenth recurrence

**There is no agent status anywhere in the backend.** No `status` column, no health signal, no heartbeat — the worker has no HTTP surface to ask (§2.1).

Cookbook 9 §0 set the binding rule: **never render a status the backend did not measure.** So:

- **No `StatusChip` on this page at all.** An `online`/`offline` chip would be fabricated, and `StatusChip` returns `null` for unknown keys anyway (`const def = STATUS[status]; if (!def) return null`), so a wrong key renders an invisible cell — the exact blank-chip failure seen eight times already.
- Structural facts render as **`Token`**: `Entry point`, `Terminal`, `Specialist`, `Unrecognized`.
- "Has this persona handled traffic in the window?" is expressed by the **numbers themselves** (`0` turns, `—` last seen), not by a chip pretending to be liveness.

**Twelfth consecutive cookbook with zero changes to `status.ts`.**

### §5.6 — `src/routes/agents.tsx`

```tsx
import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Bot } from "lucide-react"

import { PageSection } from "@/components/nexus/app-topbar"
import { HeroStat, StatCard } from "@/components/nexus/blocks"
import {
	EmptyState,
	Segmented,
	TableShell,
	Td,
	Th,
	Token,
} from "@/components/nexus/primitives"
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states"
import { AgentDetail } from "@/components/nexus/agent-detail"
import { getAgentActivity } from "@/lib/api/agents.server"
import { agentKeys } from "@/lib/api/query-keys"
import { errorMessage } from "@/lib/api/errors"
import { formatInteger } from "@/lib/nexus/format"
import {
	formatLastSeen,
	mergeAgentRows,
	routesLabel,
	sharePercent,
	type AgentRow,
} from "@/lib/nexus/agent-view"

const WINDOWS = [7, 14, 30] as const

export const Route = createFileRoute("/agents")({
	component: AgentsPage,
	head: () => ({
		meta: [
			{ title: "Agents — Nexus" },
			{
				name: "description",
				content:
					"The persona graph: entry, specialists and terminal escalation, with observed activity.",
			},
		],
	}),
})

function AgentsPage() {
	const [days, setDays] = useState<number>(30)
	const [selected, setSelected] = useState<AgentRow | null>(null)

	const activity = useQuery({
		queryKey: agentKeys.activity(days),
		queryFn: () => getAgentActivity({ data: { days } }),
	})

	const totalTurns = activity.data?.total_turns ?? 0
	const rows = activity.data
		? mergeAgentRows(activity.data.agents, totalTurns)
		: []
	const unrecognized = rows.filter((row) => row.catalog === null)
	const idle = rows.filter((row) => row.catalog !== null && row.turns === 0)

	return (
		<>
			<PageSection className="grid gap-sp-6 xl:grid-cols-4">
				<HeroStat
					label="Attributed turns"
					value={formatInteger(totalTurns)}
					context={`Across ${days} days`}
				/>
				<StatCard
					label="Personas deployed"
					value={formatInteger(rows.length)}
					context="Catalog plus observed"
				/>
				<StatCard
					label="Idle in window"
					value={formatInteger(idle.length)}
					context="No attributed turns"
				/>
				<StatCard
					label="Unrecognized"
					value={formatInteger(unrecognized.length)}
					context="Observed but not in catalog"
				/>
			</PageSection>

			<PageSection>
				<TableShell
					toolbar={
						<Segmented
							options={WINDOWS.map((value) => ({
								label: `${value}d`,
								value: String(value),
							}))}
							value={String(days)}
							onChange={(next) => setDays(Number(next))}
						/>
					}
					head={
						<tr>
							<Th>Persona</Th>
							<Th>Role in graph</Th>
							<Th align="right">Attributed turns</Th>
							<Th align="right">Share</Th>
							<Th align="right">Sessions</Th>
							<Th align="right">Last seen</Th>
						</tr>
					}
				>
					{activity.isPending ? <TableSkeleton rows={5} cols={6} /> : null}

					{activity.isError ? (
						<TableErrorRow
							colSpan={6}
							message={errorMessage(activity.error)}
							onRetry={() => activity.refetch()}
						/>
					) : null}

					{activity.isSuccess && rows.length === 0 ? (
						<tr>
							<Td colSpan={6}>
								<EmptyState
									icon={Bot}
									title="No persona activity"
									description="No turns were attributed to a persona in this window."
								/>
							</Td>
						</tr>
					) : null}

					{activity.isSuccess
						? rows.map((row) => (
								<tr
									key={row.className}
									onClick={() => setSelected(row)}
									className="cursor-pointer transition-colors duration-[120ms] hover:bg-surface-3"
								>
									<Td>
										<span className="min-w-0">
											<span className="t-ui block truncate text-ink-1">
												{row.label}
											</span>
											<span className="t-caption block truncate text-ink-4">
												{row.className}
											</span>
										</span>
									</Td>
									<Td>
										{row.catalog === null ? (
											<Token mono={false}>Unrecognized</Token>
										) : (
											<span className="flex items-center gap-sp-4">
												{row.catalog.entryPoint ? (
													<Token mono={false} strong>
														Entry point
													</Token>
												) : null}
												<Token mono={false}>{routesLabel(row.catalog)}</Token>
											</span>
										)}
									</Td>
									<Td align="right">
										<span className="t-mono text-ink-3">
											{formatInteger(row.turns)}
										</span>
									</Td>
									<Td align="right">
										<span className="t-mono text-ink-3">
											{sharePercent(row.turnShare)}
										</span>
									</Td>
									<Td align="right">
										<span className="t-mono text-ink-3">
											{formatInteger(row.sessions)}
										</span>
									</Td>
									<Td align="right">
										<span className="t-mono text-ink-3">
											{formatLastSeen(row.lastSeen)}
										</span>
									</Td>
								</tr>
							))
						: null}
				</TableShell>
			</PageSection>

			{selected ? (
				<AgentDetail row={selected} onClose={() => setSelected(null)} />
			) : null}
		</>
	)
}
```

**Call-site checks carried forward.** Feature 1 discovered that `SearchInput` does not forward `value`/`onChange`; this page ships **no search** (five rows), so that trap is avoided entirely. `Td` may not forward `colSpan` — used once, in the empty state. **Verify both before wiring** (§6, check 7). If `Td` drops `colSpan`, use a bare `<td colSpan={6} className="h-[52px] t-ui text-ink-2">`.

### §5.7 — `src/components/nexus/agent-detail.tsx`

The Modal from Feature 1 — which **portals to `document.body`**, because `PageSection` carries `.rise` with `transform: translateY(8px)`, creating a containing block that clips `position: fixed` children. Any overlay on this page must portal.

```tsx
import { Modal } from "@/components/nexus/modal"
import { Token } from "@/components/nexus/primitives"
import {
	AGENT_LANGUAGES,
	DOMAIN_CATALOG,
	INSTRUCTION_LAYERS,
} from "@/lib/nexus/agent-catalog"
import { formatInteger } from "@/lib/nexus/format"
import { formatLastSeen, sharePercent, type AgentRow } from "@/lib/nexus/agent-view"

export function AgentDetail({
	row,
	onClose,
}: {
	row: AgentRow
	onClose: () => void
}) {
	const entry = row.catalog
	const owned = entry?.owns
		? DOMAIN_CATALOG.find((domain) => domain.key === entry.owns)
		: null
	const routed = entry
		? DOMAIN_CATALOG.filter((domain) => entry.routes.includes(domain.key))
		: []

	return (
		<Modal title={row.label} onClose={onClose}>
			<div className="grid gap-sp-7">
				<section>
					<p className="t-caption text-ink-4">{row.className}</p>
					<p className="t-ui mt-sp-4 text-ink-2">
						{entry?.role ??
							"This persona was observed in call turns but is not present in the transcribed catalog. The catalog is likely stale against the deployed agent worker."}
					</p>
					{entry ? (
						<p className="t-caption mt-sp-4 text-ink-4">Source: {entry.source}</p>
					) : null}
				</section>

				<section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
					<p className="t-label text-ink-3">Observed activity</p>
					<div className="mt-sp-5 grid grid-cols-3 gap-sp-5">
						<div>
							<p className="t-mono-l text-ink-1">{formatInteger(row.turns)}</p>
							<p className="t-caption text-ink-4">Attributed turns</p>
						</div>
						<div>
							<p className="t-mono-l text-ink-1">{sharePercent(row.turnShare)}</p>
							<p className="t-caption text-ink-4">Share of turns</p>
						</div>
						<div>
							<p className="t-mono-l text-ink-1">{formatLastSeen(row.lastSeen)}</p>
							<p className="t-caption text-ink-4">Last seen</p>
						</div>
					</div>
				</section>

				{entry ? (
					<section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
						<p className="t-label text-ink-3">Position in the persona graph</p>
						<div className="mt-sp-5 flex flex-wrap gap-sp-4">
							{entry.entryPoint ? (
								<Token mono={false} strong>
									Starts every call
								</Token>
							) : null}
							{entry.terminal ? (
								<Token mono={false} strong>
									Final escalation point
								</Token>
							) : null}
							{owned ? <Token mono={false}>Owns {owned.key}</Token> : null}
							{routed.map((domain) => (
								<Token key={domain.key} mono={false}>
									Routes {domain.key}
								</Token>
							))}
						</div>
						{entry.terminal ? (
							<p className="t-caption mt-sp-5 text-ink-4">
								Derived, not configured: this persona has no escalate_to_manager
								tool, which is what makes it terminal.
							</p>
						) : null}
					</section>
				) : null}

				{owned ? (
					<section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
						<p className="t-label text-ink-3">Spoken transition line</p>
						<p className="t-caption mt-sp-4 text-ink-4">
							What the caller hears when routed here.
						</p>
						<div className="mt-sp-5 grid gap-sp-4">
							{AGENT_LANGUAGES.map((code) => (
								<div key={code} className="flex items-start gap-sp-5">
									<Token>{code}</Token>
									<span
										className="t-ui text-ink-2"
										dir={code === "ar" ? "rtl" : "ltr"}
									>
										{owned.lines[code]}
									</span>
								</div>
							))}
						</div>
					</section>
				) : null}

				<section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
					<p className="t-label text-ink-3">Instruction layers</p>
					<p className="t-caption mt-sp-4 text-ink-4">
						Assembled at construction from the persona's registered tools. Read-only:
						personas are code, not configuration.
					</p>
					<div className="mt-sp-5">
						{INSTRUCTION_LAYERS.map((layer) => (
							<div
								key={layer.name}
								className="border-b border-stroke-subtle py-sp-5 last:border-b-0"
							>
								<span className="t-ui text-ink-1">{layer.name}</span>
								{layer.conditional ? (
									<span className="t-label ml-auto text-ink-3">
										{layer.conditional}
									</span>
								) : null}
								<p className="t-caption mt-sp-4 text-ink-4">{layer.detail}</p>
							</div>
						))}
					</div>
				</section>
			</div>
		</Modal>
	)
}
```

**Arabic.** `DOMAIN_CATALOG` carries real Arabic copy. The transition-line block sets `dir="rtl"` on the Arabic string only. This is a correctness fix, not a design-system change: no colour, spacing or type token is introduced. Without it the Arabic line renders with reversed punctuation placement.

### §5.8 — `query-keys.ts`

```ts
export const agentKeys = {
	all: ["agents"] as const,
	activity: (days: number) => ["agents", "activity", days] as const,
}
```

### §5.9 — `nav.ts`

Add under **INSIGHTS**, beside `/analytics` and C8's `/decisions`:

```ts
{ label: "Agents", to: "/agents", shortcut: "G G" },
```

**Shortcut audit:** `G A` = Advisors (Feature 1), `G D` = Availability (Feature 2), `G K` = Decisions (proposed, C8). `G G` is free. Also add the `PAGE_META` entry alongside the existing routes, matching the shape already in the file.

This is the **second** nav change in twelve cookbooks (after C8). `routeTree.gen.ts` regenerates on dev-server start — **never hand-edit it**; confirm the generated diff contains exactly one `/agents` line.

---

## §6 — Validation checklist

Backend:

1. `GET /api/v1/agents/activity` with `X-Role: superviseur` → `200` and the §4 shape.
2. Same with `X-Role: conseiller` → `403 requires role >= superviseur`.
3. `?days=0` and `?days=9999` → clamped to `1` and `365`; no error.
4. `?days=abc` → FastAPI `422` (int coercion). Acceptable; not a 500.
5. Empty database → `{"window_days":30,"total_turns":0,"total_sessions":0,"agents":[]}` — **not** a 500 and not `null`.
6. Confirm **V1**: `Turn` has no dependency on `created_at` in the shipped query (`grep -n "Turn.created_at" apps/business-api/src/business_api/repositories.py` → no hits).

Frontend:

7. `Td` forwards `colSpan`; if not, apply the §5.6 fallback. `Segmented` renders with `type="button"` (Feature 1 fix) and does not submit.
8. `Modal` opens above the topbar (`--z-topbar: 30`) and is not clipped by `PageSection`'s `.rise` transform.
9. Loading → `TableSkeleton rows={5} cols={6}`. Error → `TableErrorRow` with a working Retry. Empty → `EmptyState`.
10. Kill the business API → the table shows the error row, not a blank page; Retry recovers once it is back.
11. All five catalog personas appear even with an empty database, each with `0` turns and `—` last seen. **This is the union behaviour of §0.3 — verify it explicitly.**
12. Insert a fake row: `UPDATE conversation.turns SET active_agent='ExperimentalAgent' WHERE ...` on one turn → an **"Unrecognized"** row appears labelled *"Experimental"*, and the "Unrecognized" stat card reads `1`. Revert afterwards.
13. Switching 7d/14d/30d refetches under a distinct query key and the hero context text follows.
14. Arabic transition line renders RTL; French and English render LTR.
15. Network tab: **zero** direct requests to `:8108` — everything through the TanStack server proxy.
16. Shares sum to ~100% (rounding may leave ±1%); `<1%` renders for tiny non-zero shares rather than `0%`.

Repo hygiene:

17. `tsc --noEmit` clean.
18. `lint` returns to the exact **36-problem baseline** (28 prettier errors + 8 warnings).
19. `build` exits `0`.
20. `git diff --stat` touches only the §5.1 files plus the two backend files. **Zero** new npm dependencies.
21. `grep -n 'rgb(\|#[0-9a-fA-F]\{3,6\}' src/routes/agents.tsx src/components/nexus/agent-detail.tsx src/lib/nexus/agent-view.ts src/lib/nexus/agent-catalog.ts` → no hits.
22. `grep -n 'getDay(\|getHours(\|new Date(\|toLocaleString(' src/lib/nexus/agent-view.ts` → no hits.
23. `grep -n 'StatusChip' src/routes/agents.tsx src/components/nexus/agent-detail.tsx` → no hits (§5.5).
24. `git diff src/lib/nexus/status.ts` → empty.

---

## §7 — Cross-cookbook consistency

| Convention | This cookbook |
|---|---|
| Empty-filter convention | N/A — the only parameter is `days`, always sent, whitelisted to `[7,14,30]` client-side and clamped 1–365 server-side (C9 pattern) |
| `formatInteger` over `toLocaleString` | Followed — and note C10 self-reported three `toLocaleString` call sites to swap at apply time; this cookbook does not repeat that mistake |
| Never render an unmeasured status | Followed to its conclusion: **no chips at all** (§5.5) |
| Remove, don't disable | Followed: no persona-mutation controls ship (§0.1) |
| Overlays portal to `document.body` | Followed (§5.7) |
| `requireRole` is a factory | Followed (§5.2) |
| `POST` for mutations (CSRF) | N/A — read-only page |
| Backend additions are access, not logic | Followed (§3.2) |

---

## §8 — Open questions and things needing your confirmation

**§8.1 — MUST-VERIFY before shipping the "Attributed turns" label (V2).** `base_agent.py` stamps `active_agent` on `speaker="caller"` turns. If `conversation/writer.py` also stamps it on `speaker="agent"` turns, the counts roughly double and the metric means something different. **Read `apps/agent-worker/src/conversation/writer.py` and confirm before this page is called done.** If both speakers are stamped, either add `.filter(Turn.speaker == "caller")` or rename the column to "Turns". I did not guess.

**§8.2 — Persona contract violations are invisible in production.** `STRICT_PERSONA_CONTRACT` is never set, so `enforce_contract` degrades to `logger.error` (§2.4). A persona instructed to call a tool it does not own is a real defect class — it is what the whole `instruction_kit` refactor exists to prevent — yet operators have no way to see it. Two options, both needing your call: (a) set `STRICT_PERSONA_CONTRACT=1` in CI only, so violations fail the build but never kill a live call; (b) additionally write violations to the audit ledger at worker startup so they surface in Cookbook 10's audit panel. **(a) is cheap and safe and I recommend it regardless.** (b) is new business logic and needs approval.

**§8.3 — Should the page show the full persona prose?** I chose to show the **layer structure**, not the assembled prompt text. Rendering the complete instruction block would require transcribing five `core_instructions` strings into the frontend — hundreds of lines that go stale silently and have no drift detector (unlike class names, which §0.3 catches). If you want the actual prompt text visible in the dashboard, the honest way is a build step that emits the personas to JSON, not hand-transcription. Say if you want that scoped.

**§8.4 — `total_sessions` over-counts deliberately.** A call handled by Triage then Billing contributes to both. It is a share denominator, not a session census. The real session count is `system_overview().metrics.total_calls` (Feature 9). If you would rather the card show true distinct sessions, that is a second query — tell me and I will add it.

**§8.5 — The handoff graph is not measured, only declared.** The page shows who *can* route where (from tool sets) but not how often a handoff actually happened, because no handoff event is persisted — only the resulting `active_agent` on subsequent turns. Reconstructing real transitions means ordering turns by `turn_index` per session and detecting changes in `active_agent`: entirely feasible as a second endpoint, genuinely useful (it would show, for example, that Triage misroutes to Billing 30% of the time), but it is a **new analytical capability**, so it needs your approval rather than my assumption.

**§8.6 — Two domains-vs-agents asymmetries worth a product decision.** (i) `domains.py` declares three domains, but `ManagerAgent` and `TriageAgent` have none — the page handles this, but if you intend Manager to become a routable domain that is a source change. (ii) `KNOWN_TOOL_VOCABULARY` lists ticketing tools (`create_support_ticket`, `mark_ticket_resolved`, …) that connect this page conceptually to Cookbook 5, but `tools/ticket_tools.py` (`942d9b9d`) remains **unread** — it is also still outstanding for the Phase-2 S2 silence audit.

**§8.7 — This page is the natural home for the Phase-2 fix's observability.** The Phase-2 patch (`guards.py`, `ensure_identity_verified` wrapped in `context.foreground()`) addresses the silent-turn-after-tool bug. Nothing currently reports how often that path triggers. Once applied, a counter here would tell you whether the fix is holding in production. Out of scope for this cookbook; flagged because it is the right place.

---

## §9 — What remains after this cookbook

With Feature 12, **every feature you named in the Phase-3 brief now has a cookbook.** What is left is not admin surfaces but genuine gaps:

1. **`/rules`** — orphan template, no backend (C7 §8.1).
2. **`/conversations`** — orphan template; C8 §9.1–§9.2 flagged that its reply composer and ingestion panel duplicate `/knowledge`.
3. **Real service health probes** (C9 §8.1) — the eleven hardcoded `"online"` strings in `system_overview()`. Needs approval; now doubly relevant since §2.1 proves the agent worker cannot be health-checked over HTTP at all.
4. **No user store** (C10 §8.3, C11 §0.1) — members, roles and API keys are unbuilt business logic, and admin auth is still two env vars.
5. **Two known unguarded 500s** in `main.py`: the C4 `max_frustration` `float(None)`, reachable four ways, and the C11 non-UUID `customer_id`. Both drafted, neither shipped, per Constraint 2.
6. **Modelled but unexposed data** (C11 §8.6): `CustomerInteraction`, `Payment`, `PaymentPlan`, consent records.

My recommendation for what to do next: **stop adding surfaces and apply what exists.** Cookbooks 3–12 are designed but unapplied, and each one that sits unapplied increases the chance that a shared file (`query-keys.ts`, `nav.ts`, `repositories.py`, `main.py`) drifts from what these documents assume. Cookbooks 9 and 12 in particular have a hard ordering dependency: C12 will not compile unless C9's `delta?` change to `blocks.tsx` is in place.
