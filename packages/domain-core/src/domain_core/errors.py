"""Domain error hierarchy (framework-free)."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""


class PolicyDeniedError(DomainError):
    """Raised when a sensitive action is REFUSED by the Policy engine."""


class EscalationRequiredError(DomainError):
    """Raised when the Policy engine returns ESCALATE."""


class IdentityVerificationError(DomainError):
    """Raised when step-up identity verification fails."""


class ExternalSystemUnavailableError(DomainError):
    """Raised when a legacy system is unreachable (drives degraded-mode handling)."""