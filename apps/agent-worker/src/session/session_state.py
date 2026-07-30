"""Per-session state carried across agents/tasks (cookbook section 17). No business logic."""
from __future__ import annotations

import hashlib
import json
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
    human_transfer_outcome: str | None = None
    escalation_reason: str | None = None

    # --- conversation persistence (P3) ---
    conversation_writer: object | None = None
    session_db_id: str | None = None

    _idempotency_keys: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def _operation_fingerprint(action_type: str, payload: dict | None) -> str:
        """Stable identity of one logical operation: its type plus its business parameters."""
        if not payload:
            return action_type
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return f"{action_type}:{hashlib.sha256(body.encode()).hexdigest()[:16]}"

    def new_idempotency_key(self, action_type: str, payload: dict | None = None) -> str:
        """Return the idempotency key for ONE logical operation.

        The key is memoised per (session, action_type, business payload) and is kept as long as the
        operation has NOT been confirmed executed, so any retry (timeout, transport error) reuses it
        and can never double-charge. Once ``release_idempotency_key`` reports success, the key is
        dropped: a later request - even with identical parameters - is a genuinely NEW action and
        gets a NEW key, instead of being silently replayed as the first one.
        """
        fingerprint = self._operation_fingerprint(action_type, payload)
        if fingerprint not in self._idempotency_keys:
            seed = f"{self.session_id}:{fingerprint}:{uuid.uuid4()}"
            self._idempotency_keys[fingerprint] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[fingerprint]

    def release_idempotency_key(self, action_type: str, payload: dict | None = None) -> None:
        """Forget a completed operation's key so the next request is not treated as a retry."""
        self._idempotency_keys.pop(self._operation_fingerprint(action_type, payload), None)