"""Per-session state carried across agents/tasks (cookbook section 17). No business logic.

Holds recording consent, the rolling sentiment signal (populated in Phase 8), and the
idempotency-key store reused across action retries (Phase 7). Phase 4 replaces the
customer_context dict with a typed CustomerContext snapshot.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field


@dataclass
class SessionUserData:
    """Session-scoped, mutable state shared by the active persona, tasks and tools."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "fr"
    customer_context: dict | None = None  # typed CustomerContext lands in Phase 4
    recording_consent: bool | None = None
    sentiment_history: list[float] = field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    clarification_attempts: int = 0
    _idempotency_keys: dict[str, str] = field(default_factory=dict)

    def new_idempotency_key(self, action_type: str) -> str:
        """One key per (session, action_type); reused across retries so a retry is safe."""
        if action_type not in self._idempotency_keys:
            seed = f"{self.session_id}:{action_type}:{uuid.uuid4()}"
            self._idempotency_keys[action_type] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[action_type]