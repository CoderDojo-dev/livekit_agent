# Version 65 — Persona Contract: Derived Routing Mandate + Domain Source of Truth

> **Base branch:** `version_64`
> **Files changed:** 7 modified, 5 new (+474 / -340)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

### Problem

The frozen `NO_DEAD_END_MANDATE` in `base_agent.py` named every `route_*` tool, even those the injecting persona did not own. A specialist agent could be instructed to call `route_to_billing` without having that tool registered — a phantom tool-call vector that only went unnoticed because the triage persona happened to own all three route tools. Additionally, routing data (spoken transition lines, tool names, domain topics) was duplicated across `routing_tools.py` and each persona's prompt, creating a maintenance hazard.

### Solution — Three-part Refactor

**1. `agents/domains.py` (new)** — Single source of truth for every specialist domain. Each `Domain` dataclass holds:
- `key` — stable internal identifier
- `route_condition` / `own_topics` — LLM-facing prose for routing mandate generation
- `route_tool` — the `@function_tool` name that performs the handoff
- `lines` — deterministic spoken transition per language (fr, ar, en)

Exports `DOMAIN_BY_KEY`, `DOMAIN_BY_ROUTE_TOOL`, `ROUTE_TOOL_NAMES`, and `SUPPORTED_LANGUAGES`.

**2. `agents/instruction_kit.py` (new)** — Pure-function module that derives each persona's full instruction block from its registered tool set:
- `routing_mandate(available)` — generates the routing mandate citing ONLY tools the persona actually owns. A persona without a `route_*` tool for domain X is told it "owns" that domain. The terminal persona (Manager — lacks `escalate_to_manager`) gets a "final escalation point" mandate pointing at `transfer_to_human`.
- `build_persona_instructions(core, available)` — assembles core + knowledge rule (if `knowledge_search` is available) + routing mandate + closing protocol + language policy + TTS lock.
- `enforce_contract(persona, instructions, available)` — validates that no instruction cites an unavailable tool (raises in CI under `STRICT_PERSONA_CONTRACT=1`, logs in production).
- `KNOWN_TOOL_VOCABULARY` — explicit catalog of every known `@function_tool` name, validated by a static check script.

**3. New `BaseTelecomAgent` constructor** — Accepts `core_instructions` (domain prose only) and `capabilities` (for MCP toolsets). Full instructions are derived automatically. Old `instructions=` path retained for backward compatibility but validated against the tool set.

### Files Changed

| File | Change |
|------|--------|
| `src/agents/domains.py` | **NEW** — Domain dataclass + lookup tables |
| `src/agents/instruction_kit.py` | **NEW** — Instruction builder + contract enforcement |
| `src/agents/base_agent.py` | Refactored `__init__` with `core_instructions`/`capabilities`; shared layers moved to `instruction_kit.py` |
| `src/agents/billing_agent.py` | Extracted `_CORE` to module level; uses `core_instructions=` with `capabilities={"knowledge_search"}` |
| `src/agents/account_services_agent.py` | Same pattern |
| `src/agents/technical_agent.py` | Same pattern |
| `src/agents/triage_agent.py` | Same pattern |
| `src/agents/manager_agent.py` | Same pattern |
| `src/tools/routing_tools.py` | Removed local `_ROUTE_LINES`; reads from `DOMAIN_BY_KEY` |
| `tests/test_persona_contract.py` | **NEW** — 10 tests: invariant, ownership, non-regression, layer presence, domain integrity |
| `scripts/persona_contract_checks.py` | **NEW** — 30+ static checks for module health and tool coverage |
| `scripts/prompt_snapshot.py` | **NEW** — Offline persona prompt dumper with stubbed TTS |

### Verification

- `tests/test_persona_contract.py::test_no_persona_is_told_to_use_a_tool_it_lacks` — the v64 invariant that catches phantom tool references.
- `test_triage_mandate_is_textually_unchanged_from_v63` — byte-identical non-regression for the triage persona.
- `python -m pytest apps/agent-worker/tests/test_persona_contract.py -v` runs offline (no LiveKit, no TTS).
- `python scripts/persona_contract_checks.py` performs 30+ static assertions.
