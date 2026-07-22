"""PII-safe realtime frontend events.

The worker publishes only a tool call identifier, safe display label, tool name,
and terminal status. Tool arguments and outputs are intentionally excluded
because they can contain customer, authentication, billing, or account data.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from livekit.agents import FunctionToolsExecutedEvent

logger = logging.getLogger(__name__)

TOOL_EVENT_TOPIC = "telecom.tool-events"

_TOOL_LABELS = {
    "knowledge_search": "Searching telecom knowledge",
    "get_invoice_summary": "Reading invoice information",
    "get_balance_summary": "Reading account balance",
    "get_plan_details": "Reading plan details",
    "route_to_billing": "Routing to billing support",
    "route_to_technical": "Routing to technical support",
    "escalate_to_manager": "Preparing specialist handoff",
    "verify_with_known_element": "Verifying identity",
    "record_consent": "Recording consent choice",
    "change_plan": "Checking plan change",
    "execute_payment": "Processing payment request",
    "unblock_sim": "Checking SIM unblock",
    "replace_sim": "Preparing SIM replacement",
    "create_ticket": "Creating support ticket",
    "schedule_callback": "Scheduling callback",
}


def _safe_label(tool_name: str) -> str:
    """Return a bounded display label without exposing arguments or results."""
    if tool_name in _TOOL_LABELS:
        return _TOOL_LABELS[tool_name]

    cleaned = re.sub(
        r"[^a-zA-Z0-9_ -]",
        "",
        tool_name,
    ).strip()

    cleaned = cleaned.replace("_", " ")
    return cleaned[:64].strip().title() or "Service action"


class FrontendEventPublisher:
    """Publish non-blocking, bounded events over a LiveKit text stream."""

    def __init__(self, room: Any) -> None:
        self._room = room
        self._tasks: set[asyncio.Task[None]] = set()

    def publish_tool_batch(
        self,
        event: FunctionToolsExecutedEvent,
    ) -> None:
        """Publish one terminal frontend event per completed tool call."""
        for function_call, output in zip(
            event.function_calls,
            event.function_call_outputs,
            strict=False,
        ):
            status = (
                "error"
                if output is not None and output.is_error
                else "done"
            )

            payload = {
                "version": 1,
                "kind": "tool",
                "id": function_call.call_id,
                "name": function_call.name,
                "label": _safe_label(function_call.name),
                "status": status,
                "created_at": event.created_at,
            }

            self._spawn(self._send(payload))

    def _spawn(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _send(
        self,
        payload: dict[str, object],
    ) -> None:
        try:
            await self._room.local_participant.send_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                topic=TOOL_EVENT_TOPIC,
            )
        except Exception as exc:
            # UI observability must never break or delay the voice path.
            logger.debug(
                "frontend event skipped: %s",
                exc,
            )

    async def aclose(self) -> None:
        """Drain outstanding event sends during session shutdown."""
        if not self._tasks:
            return

        await asyncio.gather(
            *tuple(self._tasks),
            return_exceptions=True,
        )
        self._tasks.clear()
