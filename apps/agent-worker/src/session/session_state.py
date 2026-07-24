"""Per-session state carried across agents/tasks (cookbook section 17). No business logic."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from session.customer_context import CustomerContext


@dataclass
class SessionUserData:
    """Session-scoped, mutable state shared by the active persona, tasks and tools."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: str = "fr"
    customer_context: CustomerContext | None = None
    identity_verified: bool = False
    identity_attempts: int = 0
    verified_customer_id: str | None = None
    verification_level: str | None = None
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    verification_method: str | None = None
    verification_session_id: str | None = None
    recording_consent: bool | None = None

    # --- sentiment / escalation (Phase 8) ---
    sentiment_history: list[float] = field(default_factory=list)
    consecutive_negative_turns: int = 0
    should_offer_escalation: bool = False
    clarification_attempts: int = 0
    _clarification_pending: bool = False  # patch #5: streak de deferrals consécutifs
    current_persona_skill_tag: str = "general"
    callback_requested: bool = False
    callback_when: str | None = None
    human_transfer_announced: bool = False
    human_transfer_in_progress: bool = False
    escalation_reason: str | None = None

    # --- conversation persistence (P3) ---
    conversation_writer: object | None = None
    session_db_id: str | None = None

    _idempotency_keys: dict[str, str] = field(default_factory=dict)

    def new_idempotency_key(self, action_type: str) -> str:
        """One key per (session, action_type); reused across retries so a retry is safe."""
        if action_type not in self._idempotency_keys:
            seed = f"{self.session_id}:{action_type}:{uuid.uuid4()}"
            self._idempotency_keys[action_type] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[action_type]