"""Domain entities (objects with identity and a lifecycle). Owned per bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from domain_core.value_objects import (
    EscalationReason,
    Language,
    Money,
    Sentiment,
    Verdict,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Client:
    """Customer 360 snapshot (read-through from CRM; CRM stays system of record)."""

    customer_id: str
    full_name: str
    msisdn: str
    subscription_type: str
    preferred_language: Language = Language.FR
    is_vip: bool = False
    fraud_suspected: bool = False
    account_age_days: int = 0


@dataclass(slots=True)
class Intent:
    """What the client wants, plus extracted slots (versioned taxonomy, not free text)."""

    name: str
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass(slots=True)
class Turn:
    """A single client/agent exchange within a conversation (append-only)."""

    turn_id: str
    speaker: str  # "client" | "agent"
    text: str
    language: Language
    sentiment: Sentiment = Sentiment.NEUTRAL
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Conversation:
    """One session; turns are appended; outcome powers KPIs."""

    conversation_id: str
    channel: str
    language: Language = Language.FR
    turns: list[Turn] = field(default_factory=list)
    outcome: str | None = None  # "resolved" | "escalated"
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Decision:
    """A candidate action proposed by the Decision context, with confidence."""

    action: str
    confidence: float
    rationale: str = ""


@dataclass(slots=True)
class PolicyVerdict:
    """An immutable, audited guardrail verdict (CDC section 4.6)."""

    verdict: Verdict
    rule_id: str
    justification: str
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Action:
    """A sensitive action carrying an idempotency key (CDC section 4.7)."""

    action_id: str
    kind: str
    idempotency_key: str
    status: str = "pending"  # pending | succeeded | failed
    amount: Money | None = None
    reference: str | None = None
    retries: int = 0


@dataclass(slots=True)
class Ticket:
    """Local mirror of a GLPI ticket (never a second source of truth)."""

    ticket_id: str
    glpi_id: str | None
    subject: str
    status: str
    priority: str


@dataclass(slots=True)
class EscalationCase:
    """A human hand-off dossier (CDC section 4.9)."""

    case_id: str
    reason: EscalationReason
    summary: str
    target: str = "human"  # "manager" | "human"
    resolution: str | None = None


@dataclass(slots=True)
class ConsentRecord:
    """Per-call recording consent (CDC section 8.1)."""

    conversation_id: str
    granted: bool
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class AuditEntry:
    """A hash-chained, append-only audit record (CDC sections 8.4 / 9.3)."""

    entry_id: str
    payload: dict[str, Any]
    previous_hash: str
    entry_hash: str
    created_at: datetime = field(default_factory=_now)