"""Per-session state carried across agents/tasks (no business logic lives here)."""
from __future__ import annotations

from dataclasses import dataclass, field

from domain_core.value_objects import Language, Sentiment


@dataclass
class SessionUserData:
    """Mutable session context shared by the active persona, tasks and tools."""

    conversation_id: str
    language: Language = Language.FR
    customer_id: str | None = None
    identity_verified: bool = False
    consent_granted: bool | None = None
    sentiment: Sentiment = Sentiment.NEUTRAL
    frustration_streak: int = 0
    clarification_attempts: int = 0
    identity_attempts: int = 0
    snapshot: dict = field(default_factory=dict)