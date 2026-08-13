"""NotificationService: render -> send -> record. Durable log to billing.notifications (spec 5.2).

Live-only, no mock fallback. If a channel is unconfigured or the provider rejects the message,
sent=False is returned with the actual reason. The DB record is written with status='failed'
and that same reason in failure_reason (truncated to the column width).

Contact resolution is centralised here: callers pass a customer_id, never a phone/email.
The notification-service maps customer_id -> the right handle for each channel from crm.customers,
so contact details live in exactly one place and every caller stays decoupled from PII.
"""
from __future__ import annotations

import asyncio
import logging
import os

from notification_service.channels import ChannelUnavailable, get_channel
from notification_service.contacts import ContactUnavailable, resolve_recipient
from notification_service.schemas import NotifyRequest, NotifyResponse
from notification_service.templates import render

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends localized written confirmations over the selected channel and logs them."""

    def __init__(self) -> None:
        self._sent: list[dict] = []

    async def notify(self, req: NotifyRequest) -> NotifyResponse:
        """Render and send one confirmation; record it (in-memory + durable log).

        Returns sent=False with a reason when the channel is unconfigured, the provider fails,
        or the customer cannot be resolved, rather than raising or faking success.
        """
        # Resolve the recipient centrally: callers pass a customer_id, never a phone/email.
        # An explicit req.to still wins (useful for tests and one-off sends).
        language = req.language
        recipient = req.to
        if not recipient:
            try:
                recipient, preferred = await asyncio.to_thread(
                    resolve_recipient, req.customer_id, req.channel
                )
                if preferred and not req.language_was_set:
                    language = preferred
            except ContactUnavailable as exc:
                logger.warning("notify no-contact [%s/%s]: %s", req.channel, req.template, exc)
                self._record(req, status="failed", reference="", reason=str(exc))
                return NotifyResponse(sent=False, reference="", channel=req.channel,
                                      reason=str(exc))

        body = render(req.template, language or "fr", req.params)
        try:
            channel = get_channel(req.channel)
            reference = await channel.send(recipient, body)
            sent = True
            reason = ""
            status = "sent"
        except ChannelUnavailable as exc:
            reference = ""
            sent = False
            reason = str(exc)
            status = "failed"
        except Exception as exc:
            reference = ""
            sent = False
            reason = f"{type(exc).__name__}: {exc}"
            status = "failed"

        self._record(req, status=status, reference=reference, reason=reason)
        return NotifyResponse(sent=sent, reference=reference, channel=req.channel, reason=reason)

    def _record(self, req: NotifyRequest, status: str, reference: str,
                reason: str = "") -> None:
        self._sent.append({
            "customer_id": req.customer_id, "channel": req.channel,
            "template": req.template, "reference": reference,
            "sent": status == "sent", "reason": "" if status == "sent" else reason,
        })
        if not os.getenv("DATABASE_URL"):
            logger.warning(
                "notification NOT persisted, DATABASE_URL unset [%s/%s] status=%s",
                req.channel, req.template, status,
            )
            return
        try:
            self._persist(req, status, reason)
        except Exception:
            logger.exception(
                "notification log write FAILED [%s/%s] status=%s customer=%s",
                req.channel, req.template, status, req.customer_id,
            )

    @staticmethod
    def _persist(req: NotifyRequest, status: str, reason: str = "") -> None:
        from persistence.engine import session_scope
        from persistence.models.billing import Notification
        from persistence.util import to_uuid

        with session_scope() as session:
            session.add(Notification(
                customer_id=to_uuid(req.customer_id),
                channel=req.channel,
                template_code=req.template,
                status=status,
                failure_reason=(reason[:200] or None) if status == "failed" else None,
            ))

    @property
    def sent(self) -> list[dict]:
        return list(self._sent)
