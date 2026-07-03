"""NotificationService: render -> send -> record. Durable log to billing.notifications (spec 5.2).

The DB write is best-effort and gated on DATABASE_URL, so the service still runs (in-memory only)
with no database configured. An in-memory list is kept for the /sent inspection endpoint.
"""
from __future__ import annotations

import asyncio
import logging
import os

from notification_service.channels import get_channel
from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.templates import render

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends localized written confirmations over the selected channel and logs them."""

    def __init__(self) -> None:
        self._sent: list[dict] = []

    async def notify(self, req: NotifyRequest) -> NotifyResponse:
        """Render and send one confirmation; record it (in-memory + durable log)."""
        body = render(req.template, req.language, req.params)
        channel = get_channel(req.channel)
        reference = await channel.send(req.to or req.customer_id, body)

        self._sent.append(
            {"customer_id": req.customer_id, "channel": req.channel, "template": req.template, "reference": reference}
        )
        if os.getenv("DATABASE_URL"):
            try:
                await asyncio.to_thread(self._persist, req)
            except Exception as exc:
                logger.warning("notification log write skipped: %s", exc)

        return NotifyResponse(sent=True, reference=reference, channel=req.channel)

    @staticmethod
    def _persist(req: NotifyRequest) -> None:
        from persistence.engine import session_scope
        from persistence.models.billing import Notification
        from persistence.util import to_uuid

        with session_scope() as session:
            session.add(Notification(
                customer_id=to_uuid(req.customer_id),
                channel=req.channel,
                template_code=req.template,
                status="sent",
            ))

    @property
    def sent(self) -> list[dict]:
        return list(self._sent)