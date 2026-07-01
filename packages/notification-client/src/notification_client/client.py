"""Strategy over channels. Phase 9 wires real SMS/WhatsApp/Email gateways."""
from __future__ import annotations

import logging

from domain_core.ports.notification import NotificationPort

logger = logging.getLogger(__name__)


class ChannelStrategyNotifier(NotificationPort):
    """Select a channel strategy and dispatch. Scaffold: logs the intent."""

    async def send(self, channel: str, to: str, template: str, data: dict) -> None:
        logger.info("notify channel=%s to=%s template=%s", channel, to, template)