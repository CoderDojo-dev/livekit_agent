"""Per-session state carried across agents/tasks (cookbook section 17). No business logic."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from session.customer_context import CustomerContext

# A repeat of an identical action inside this window after a success is treated as a machine
# duplicate (LLM double tool-call under interruption/retry) and replays the first result.
# After the window, an identical request is a deliberate new action and gets a new key.
_DUPLICATE_WINDOW_S = 60.0


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
    # P1-2 - tools.session_flow_tools.end_conversation already assigns this when the caller
    # confirms they need nothing else. The dataclass has no slots, so the assignment silently
    # created an undeclared attribute; declaring it makes the graceful close visible to type
    # checkers and to _derive_disposition. False = the call did not end through the close tool.
    conversation_ending: bool = False
    offer_count: int = 0
    user_refused_manager: bool = False
    can_hardfail: bool = True
    caller_turn_index: int = 0
    handoff_count: int = 0
    last_handoff_turn: int = 0

    # --- conversation persistence (P3) ---
    conversation_writer: object | None = None
    session_db_id: str | None = None

    _idempotency_keys: dict[str, str] = field(default_factory=dict)
    _completed_at: dict[str, float] = field(default_factory=dict)  # fingerprint -> monotonic ts

    @staticmethod
    def _operation_fingerprint(action_type: str, payload: dict | None) -> str:
        """Stable identity of one logical operation: its type plus its business parameters."""
        if not payload:
            return action_type
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return f"{action_type}:{hashlib.sha256(body.encode()).hexdigest()[:16]}"

    def new_idempotency_key(self, action_type: str, payload: dict | None = None) -> str:
        """Return the idempotency key for ONE logical operation.

        The key is memoised per (session, action_type, business payload) and kept while the
        operation is unconfirmed, so any retry (timeout, transport error) reuses it and can never
        double-charge. After ``mark_operation_completed`` the key is RETAINED for
        ``_DUPLICATE_WINDOW_S``: an identical request inside the window is a duplicate of an action
        that already succeeded, so the same key is returned and execution replays the recorded
        success instead of running again. Once the window expires, an identical request is a
        deliberate new action and receives a fresh key.
        """
        fingerprint = self._operation_fingerprint(action_type, payload)
        completed_at = self._completed_at.get(fingerprint)
        if completed_at is not None:
            key = self._idempotency_keys.get(fingerprint)
            if key is not None and time.monotonic() - completed_at < _DUPLICATE_WINDOW_S:
                return key  # duplicate of a just-succeeded action -> server replays it
            # Window expired: forget the old operation entirely, then mint below.
            self._completed_at.pop(fingerprint, None)
            self._idempotency_keys.pop(fingerprint, None)
        if fingerprint not in self._idempotency_keys:
            seed = f"{self.session_id}:{fingerprint}:{uuid.uuid4()}"
            self._idempotency_keys[fingerprint] = hashlib.sha256(seed.encode()).hexdigest()
        return self._idempotency_keys[fingerprint]

    def mark_operation_completed(self, action_type: str, payload: dict | None = None) -> None:
        """Record that the operation executed, starting the duplicate-replay window.

        The key is deliberately NOT dropped: dropping it is what let an immediate duplicate mint
        a fresh key and execute twice.
        """
        self._completed_at[self._operation_fingerprint(action_type, payload)] = time.monotonic()