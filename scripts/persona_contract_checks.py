#!/usr/bin/env python3
"""Static contract checks for the v64 persona-instruction refactor.

Usage:
    python3 scripts/persona_contract_checks.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "agent-worker" / "src"
AGENTS = SRC / "agents"
TESTS = ROOT / "apps" / "agent-worker" / "tests"

PERSONA_FILES = {
    "TriageAgent": AGENTS / "triage_agent.py",
    "BillingAgent": AGENTS / "billing_agent.py",
    "AccountServicesAgent": AGENTS / "account_services_agent.py",
    "TechnicalAgent": AGENTS / "technical_agent.py",
    "ManagerAgent": AGENTS / "manager_agent.py",
}

_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    _results.append((label, bool(condition)))
    print(f"{'OK  ' if condition else 'FAIL'} | {label}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- A. Les nouveaux modules existent et sont autonomes --------------------- #
print("\n== A. modules ==")
domains_src = read(AGENTS / "domains.py")
kit_src = read(AGENTS / "instruction_kit.py")
check("agents/domains.py present", bool(domains_src))
check("agents/instruction_kit.py present", bool(kit_src))
check(
    "domains.py imports nothing from the project (no import cycle possible)",
    not re.search(r"^\s*from (agents|tools|tasks|clients|providers|session)\.", domains_src, re.M),
)
check("domains.py declares exactly 3 domains", domains_src.count("    Domain(\n") == 3)
for language in ("fr", "ar", "en"):
    check(
        f"domains.py declares a spoken line for '{language}' in all 3 domains",
        domains_src.count(f'"{language}": "') == 3,
    )


# --- B. Le mandat figé n'est plus injecté ---------------------------------- #
print("\n== B. frozen mandate retired ==")
for persona, path in PERSONA_FILES.items():
    src = read(path)
    check(f"{persona} no longer calls merge_instructions", "merge_instructions(" not in src)
    check(f"{persona} no longer references NO_DEAD_END_MANDATE", "NO_DEAD_END_MANDATE" not in src)
    check(f"{persona} passes core_instructions", "core_instructions=" in src)

base_src = read(AGENTS / "base_agent.py")
check(
    "base_agent still exports NO_DEAD_END_MANDATE (backward compat)",
    "NO_DEAD_END_MANDATE = (" in base_src,
)
check(
    "base_agent still exports merge_instructions (backward compat)",
    "def merge_instructions(" in base_src,
)
check(
    "base_agent derives instructions through the funnel",
    "build_persona_instructions(" in base_src and "enforce_contract(" in base_src,
)
check(
    "availability is computed AFTER the auto-injected tools are merged",
    base_src.index("merged_tools.append(switch_spoken_language)")
    < base_src.index("available = tool_names("),
)
check(
    "the contract is enforced before the SDK constructor runs",
    base_src.index("enforce_contract(") < base_src.index("super().__init__("),
)
check("strict mode is env-gated (never raises in production)", "STRICT_ENV_VAR" in kit_src)


# --- C. Capacités déclarées cohérentes avec les toolsets ------------------- #
print("\n== C. declared capabilities ==")
for persona, path in PERSONA_FILES.items():
    src = read(path)
    has_toolset = "build_knowledge_toolset()" in src
    declares = 'capabilities={"knowledge_search"}' in src
    check(f"{persona}: knowledge toolset <-> declared capability", has_toolset == declares)
    check(
        f"{persona} no longer concatenates KNOWLEDGE_ABSTENTION_RULE by hand",
        "KNOWLEDGE_ABSTENTION_RULE" not in src,
    )


# --- D. Le catalogue du validateur couvre tous les @function_tool ---------- #
print("\n== D. validator vocabulary coverage ==")
defined: set[str] = set()
for path in SRC.rglob("*.py"):
    text = read(path)
    for match in re.finditer(
        r"@function_tool\([^)]*\)\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)", text
    ):
        defined.add(match.group(1))
check("at least 20 @function_tool definitions were discovered", len(defined) >= 20)
vocabulary = set(
    re.findall(r'"([a-z_][a-z0-9_]*)",', kit_src.split("KNOWN_TOOL_VOCABULARY", 1)[1])
)
missing = sorted(defined - vocabulary)
check(f"KNOWN_TOOL_VOCABULARY covers every @function_tool (missing={missing})", not missing)


# --- E. Le miroir de test reste synchronisé avec les toolsets réels -------- #
print("\n== E. test mirror in sync ==")
test_src = read(TESTS / "test_persona_contract.py")
for persona, path in PERSONA_FILES.items():
    src = read(path)
    block = src.split("tools=[", 1)[1].split("],", 1)[0]
    registered = {
        name
        for name in re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*,", block)
        if name != "build_knowledge_toolset"
    }
    mirror = test_src.split(f'"{persona}": frozenset(', 1)[1].split("| AUTO_INJECTED", 1)[0]
    drift = sorted(name for name in registered if f'"{name}"' not in mirror)
    check(f"{persona}: test mirror lists every registered tool (drift={drift})", not drift)


# --- F. routing_tools lit la source unique -------------------------------- #
print("\n== F. routing_tools ==")
routing_src = read(SRC / "tools" / "routing_tools.py")
check("routing_tools no longer owns a local _ROUTE_LINES dict", "_ROUTE_LINES" not in routing_src)
check("routing_tools reads the single source of truth", "DOMAIN_BY_KEY[" in routing_src)
check("the three handoffs still speak a deterministic line", routing_src.count(".lines[lang]") == 3)


# --- Total ---------------------------------------------------------------- #
ok = sum(1 for _, passed in _results if passed)
failed = len(_results) - ok
print(f"\nTOTAL: {ok} OK, {failed} FAIL")
sys.exit(1 if failed else 0)
