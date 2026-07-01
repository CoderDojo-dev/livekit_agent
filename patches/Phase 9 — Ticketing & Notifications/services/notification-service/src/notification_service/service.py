"""NotificationService: render -> send -> record. Keeps a small in-memory sent-log for the demo."""
from __future__ import annotations

from notification_service.channels import get_channel
from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.templates import render


class NotificationService:
    """Sends localized written confirmations over the selected channel."""

    def __init__(self) -> None:
        self._sent: list[dict] = []

    async def notify(self, req: NotifyRequest) -> NotifyResponse:
        """Render and send one confirmation; record it for inspection."""
        body = render(req.template, req.language, req.params)
        channel = get_channel(req.channel)
        reference = await channel.send(req.to or req.customer_id, body)
        self._sent.append(
            {
                "customer_id": req.customer_id,
                "channel": req.channel,
                "template": req.template,
                "reference": reference,
            }
        )
        return NotifyResponse(sent=True, reference=reference, channel=req.channel)

    @property
    def sent(self) -> list[dict]:
        return list(self._sent)