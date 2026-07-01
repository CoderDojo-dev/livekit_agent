"""Immutable value objects shared across the domain (no identity, compared by value)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Language(str, Enum):
    """Supported conversation languages (Blueprint ADR section 5.7)."""

    FR = "fr"
    AR = "ar"
    EN = "en"


class Channel(str, Enum):
    """Client communication channels (CDC section 2.3)."""

    VOICE = "voice"
    CHAT = "chat"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"


class Verdict(str, Enum):
    """The deterministic Policy engine's three-way verdict (CDC section 4.6)."""

    AUTHORIZED = "authorized"
    REFUSED = "refused"
    ESCALATE = "escalate"


class Sentiment(str, Enum):
    """Per-turn emotional state (CDC section 4.2)."""

    SATISFIED = "satisfied"
    NEUTRAL = "neutral"
    ANNOYED = "annoyed"
    ANGRY = "angry"


class EscalationReason(str, Enum):
    """Why a conversation is handed to a human (CDC sections 5.12 / 6.4)."""

    CUSTOMER_REQUEST = "customer_request"
    FRUSTRATION = "frustration"
    OUT_OF_SCOPE = "out_of_scope"
    FRAUD_SUSPICION = "fraud_suspicion"
    VIP = "vip"
    REPEATED_NLU_FAILURE = "repeated_nlu_failure"
    REPEATED_IDENTITY_FAILURE = "repeated_identity_failure"
    POLICY_ESCALATE = "policy_escalate"


_MSISDN_RE = re.compile(r"^\+?[0-9]{6,15}$")


@dataclass(frozen=True, slots=True)
class Msisdn:
    """A subscriber phone number (lightly validated)."""

    value: str

    def __post_init__(self) -> None:
        if not _MSISDN_RE.match(self.value):
            raise ValueError(f"invalid MSISDN: {self.value!r}")


@dataclass(frozen=True, slots=True)
class Money:
    """A monetary amount; defaults to Tunisian Dinar per the mock telco dataset."""

    amount: Decimal
    currency: str = "TND"

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount must be non-negative")

    def __str__(self) -> str:
        return f"{self.amount:.3f} {self.currency}"


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """A token generated once per confirmed action and reused across retries."""

    value: str