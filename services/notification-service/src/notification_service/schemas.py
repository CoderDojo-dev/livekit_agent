"""Wire DTOs for the notification-service."""
from __future__ import annotations

from pydantic import BaseModel


class NotifyRequest(BaseModel):
    """A request to send one written confirmation to a customer."""

    customer_id: str
    to: str = ""            # contact handle; resolved server-side from customer_id in production
    channel: str = "sms"    # "sms" | "whatsapp" | "email"
    template: str = ""      # e.g. "ticket_created" | "callback_scheduled"
    language: str = "fr"    # render language (fr/ar/en)
    params: dict = {}


class NotifyResponse(BaseModel):
    """The result of a send."""

    sent: bool
    reference: str
    channel: str