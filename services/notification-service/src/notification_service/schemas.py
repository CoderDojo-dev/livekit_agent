"""Wire DTOs for the notification-service."""
from __future__ import annotations

from pydantic import BaseModel


class NotifyRequest(BaseModel):
    """A request to send one written confirmation to a customer."""

    customer_id: str
    to: str = ""              # optional override; normally resolved server-side from customer_id
    channel: str = "whatsapp" # "whatsapp" (default) | "sms" | "email"
    template: str = ""        # e.g. "ticket_created" | "callback_scheduled"
    language: str = ""        # render language (fr/ar/en); empty = use customer's preferred
    params: dict = {}

    @property
    def language_was_set(self) -> bool:
        """True when the caller explicitly chose a language (so we don't override it)."""
        return bool(self.language)


class NotifyResponse(BaseModel):
    """The result of a send."""

    sent: bool
    reference: str
    channel: str
    reason: str = ""