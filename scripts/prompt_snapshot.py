#!/usr/bin/env python3
"""Dump the final instruction block of every persona, offline.

Usage:
    python scripts/prompt_snapshot.py /tmp/prompts.json

Works unchanged on version_63 and version_64: the only thing it touches is the
TTS and MCP factories, replaced by inert stubs so no network or API key is used.
"""

import importlib
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "apps" / "agent-worker" / "src"
sys.path.insert(0, str(SRC))

PERSONAS = [
    ("agents.triage_agent", "TriageAgent"),
    ("agents.billing_agent", "BillingAgent"),
    ("agents.account_services_agent", "AccountServicesAgent"),
    ("agents.technical_agent", "TechnicalAgent"),
    ("agents.manager_agent", "ManagerAgent"),
]


class _StubTTS:
    """Inert stand-in: only its presence matters for the TTS reminder layer."""


def _stub_tts(*_args, **_kwargs):
    return _StubTTS()


def _stub_knowledge_toolset(*_args, **_kwargs):
    class _KnowledgeSearch:
        name = "knowledge_search"

    return _KnowledgeSearch()


def main(out_path: str) -> None:
    snapshot: dict[str, str] = {}
    for module_name, class_name in PERSONAS:
        module = importlib.import_module(module_name)
        # Patch the symbols in the persona's own namespace: this works whatever
        # module they were originally imported from.
        for symbol, stub in (
            ("build_persona_tts", _stub_tts),
            ("build_knowledge_toolset", _stub_knowledge_toolset),
        ):
            if hasattr(module, symbol):
                setattr(module, symbol, stub)
        agent = getattr(module, class_name)(language="fr")
        snapshot[class_name] = agent.instructions
    Path(out_path).write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote {len(snapshot)} persona prompts to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/prompts.json")
