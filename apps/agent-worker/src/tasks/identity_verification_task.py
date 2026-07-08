"""Step-up identity verification (CDC 6.5). Bounded + fail-closed: never hangs silently."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from livekit.agents import AgentTask, function_tool

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TASK_DEADLINE_S = 30.0        # no progress within this -> fail-closed to escalate
VERIFY_CALL_TIMEOUT_S = 5.0   # bound the context-service call itself


class IdentityVerificationTask(AgentTask[bool]):
    """Takes over until verified, attempts exhausted, or deadline hit (then escalate)."""

    def __init__(self, customer_id: str,
                 verify_fn: Callable[[str, str], Awaitable[bool]], chat_ctx=None) -> None:
        super().__init__(
            instructions=(
                "Before this sensitive request, verify the caller. Ask for the last four "
                "digits of their national ID (CIN). Always speak the caller's language. "
                "Be brief and reassuring."
            ),
            chat_ctx=chat_ctx,
        )
        self._customer_id = customer_id
        self._verify_fn = verify_fn
        self._attempts = 0
        self._done = False
        self._watchdog: asyncio.Task | None = None

    async def on_enter(self) -> None:
        self._arm()
        try:
            await self.session.generate_reply(instructions=(
                "Ask the caller to state the last four digits of their national ID (CIN), "
                "in their language."
            ))
        except Exception as exc:
            logger.warning("identity prompt failed: %s", exc)
            await self._fail_closed("prompt_error")

    def _arm(self) -> None:
        if self._watchdog:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._deadline())

    async def _deadline(self) -> None:
        try:
            await asyncio.sleep(TASK_DEADLINE_S)
        except asyncio.CancelledError:
            return
        await self._fail_closed("timeout")

    async def _fail_closed(self, reason: str) -> None:
        if self._done:
            return
        logger.info("identity fail-closed (%s) -> escalate", reason)
        try:
            await self.session.say(
                "Je n'ai pas pu vérifier votre identité. Je vous mets en relation avec un conseiller."
            )
        except Exception:
            pass
        self._finish(False)

    def _finish(self, verified: bool) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog:
            self._watchdog.cancel()
        self.complete(verified)

    @function_tool()
    async def verify_with_known_element(self, provided_value: str) -> None:
        """Verify identity from the last 4 digits of CIN the caller provided."""
        self._attempts += 1
        self._arm()  # reset the deadline while we work / wait for the next turn
        try:
            ok = await asyncio.wait_for(
                self._verify_fn(self._customer_id, provided_value),
                timeout=VERIFY_CALL_TIMEOUT_S,
            )
        except Exception as exc:
            logger.warning("verify_fn failed (attempt %s): %s", self._attempts, exc)
            ok = False

        if ok:
            try:
                await self.session.say("Merci, votre identité est confirmée.")
            except Exception:
                pass
            self._finish(True)
            return

        if self._attempts >= MAX_ATTEMPTS:
            await self._fail_closed("max_attempts")
            return

        try:
            await self.session.generate_reply(instructions=(
                "Tell the caller that did not match and ask once more for the last four "
                "digits of their CIN, in their language."
            ))
        except Exception as exc:
            logger.warning("identity re-prompt failed: %s", exc)
            await self._fail_closed("reprompt_error")
