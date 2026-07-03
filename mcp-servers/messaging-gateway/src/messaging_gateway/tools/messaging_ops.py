"""Outbound messaging MCP tools: send a free-form SMS / WhatsApp through the notification-service.

Kept thin on purpose: the notification-service owns channel selection, localization and the durable
log; this MCP just exposes an agent-callable surface for ad-hoc outbound messages.
"""

import os

import httpx

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8106")


async def _send(channel: str, to: str, message: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            f"{NOTIFICATION_SERVICE_URL}/notify",
            json={"customer_id": to, "to": to, "channel": channel, "template": "freeform",
                  "language": "fr", "params": {"body": message}},
        )
        ok = resp.status_code == 200 and resp.json().get("sent", False)
        return {"sent": bool(ok), "channel": channel}


async def send_sms(to: str, message: str) -> dict:
    """Send an SMS to ``to`` with ``message`` via the notification-service."""
    return await _send("sms", to, message)


async def send_whatsapp(to: str, message: str) -> dict:
    """Send a WhatsApp message to ``to`` with ``message`` via the notification-service."""
    return await _send("whatsapp", to, message)