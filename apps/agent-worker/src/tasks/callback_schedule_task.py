"""Negotiate a callback slot with the caller and book it for real.

Three properties this task must hold, in order of importance:
  1. It never promises a time the queue cannot honour: slots come from the business API,
     which knows the advisor registry and what other callers already booked.
  2. It never contradicts itself: a booked callback is confirmed, a failed one is admitted.
     The previous version could say "I could not schedule" while the journal recorded a
     callback, because the watchdog fired during the negotiation.
  3. It speaks fixed sentences in the caller's language. Times and dates are formatted, not
     generated: a hallucinated appointment is worse than no appointment.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date as _date
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from livekit.agents import AgentTask, RunContext, function_tool

from clients.callback_client import get_callback_client
from clients.notification_client import get_notification_client

logger = logging.getLogger(__name__)

# The caller now has to hear several proposals and answer: the old 25 s budget expired in the
# middle of the negotiation. The deadline is re-armed on every caller turn, so it bounds
# silence, not the conversation.
IDLE_DEADLINE_S = 45.0

_WEEKDAYS = {
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "ar": (
        "\u064a\u0648\u0645 \u0627\u0644\u0627\u062b\u0646\u064a\u0646", "\u064a\u0648\u0645 \u0627\u0644\u062b\u0644\u0627\u062b\u0627\u0621", "\u064a\u0648\u0645 \u0627\u0644\u0623\u0631\u0628\u0639\u0627\u0621",
        "\u064a\u0648\u0645 \u0627\u0644\u062e\u0645\u064a\u0633", "\u064a\u0648\u0645 \u0627\u0644\u062c\u0645\u0639\u0629", "\u064a\u0648\u0645 \u0627\u0644\u0633\u0628\u062a", "\u064a\u0648\u0645 \u0627\u0644\u0623\u062d\u062f",
    ),
}

_OFFER_TWO = {
    "fr": "Je peux vous faire rappeler {first}, ou bien {second} si vous pr\u00e9f\u00e9rez. Qu'est-ce qui vous arrange ?",
    "ar": "\u064a\u0645\u0643\u0646\u0646\u064a \u062a\u0631\u062a\u064a\u0628 \u0627\u062a\u0635\u0627\u0644 {first}\u060c \u0623\u0648 {second} \u0625\u0630\u0627 \u0643\u0646\u062a \u062a\u0641\u0636\u0644. \u0623\u064a\u0647\u0645\u0627 \u064a\u0646\u0627\u0633\u0628\u0643\u061f",
    "en": "I can have someone call you back {first}, or {second} if you prefer. Which one suits you?",
}
_OFFER_ONE = {
    "fr": "Le prochain cr\u00e9neau libre est {first}. Est-ce que \u00e7a vous convient ?",
    "ar": "\u0623\u0642\u0631\u0628 \u0645\u0648\u0639\u062f \u0645\u062a\u0627\u062d \u0647\u0648 {first}. \u0647\u0644 \u064a\u0646\u0627\u0633\u0628\u0643\u061f",
    "en": "The next free slot is {first}. Does that work for you?",
}
_NO_SLOT = {
    "fr": "Je n'ai aucun cr\u00e9neau de rappel disponible pour le moment, je pr\u00e9f\u00e8re vous le dire franchement plut\u00f4t que de vous promettre un horaire.",
    "ar": "\u0644\u0627 \u064a\u0648\u062c\u062f \u0623\u064a \u0645\u0648\u0639\u062f \u0645\u062a\u0627\u062d \u0644\u0644\u0627\u062a\u0635\u0627\u0644 \u062d\u0627\u0644\u064a\u0627\u064b\u060c \u0648\u0623\u0641\u0636\u0644 \u0623\u0646 \u0623\u0643\u0648\u0646 \u0635\u0631\u064a\u062d\u0627\u064b \u0645\u0639\u0643.",
    "en": "I have no callback slot available right now, and I would rather tell you that than promise a time.",
}
_ALTERNATIVES = {
    "fr": "Ce cr\u00e9neau n'est pas libre. Je peux vous proposer {first} ou {second}.",
    "ar": "\u0647\u0630\u0627 \u0627\u0644\u0645\u0648\u0639\u062f \u063a\u064a\u0631 \u0645\u062a\u0627\u062d. \u064a\u0645\u0643\u0646\u0646\u064a \u0623\u0646 \u0623\u0642\u062a\u0631\u062d {first} \u0623\u0648 {second}.",
    "en": "That time is not free. I can offer you {first} or {second}.",
}
_CONFIRMED = {
    "fr": "C'est not\u00e9 : un conseiller vous rappelle {when}. Vous recevez la confirmation par {channel}.",
    "ar": "\u062a\u0645 \u0627\u0644\u062a\u0633\u062c\u064a\u0644: \u0633\u064a\u062a\u0635\u0644 \u0628\u0643 \u0645\u0633\u062a\u0634\u0627\u0631 {when}. \u0633\u062a\u0635\u0644\u0643 \u0627\u0644\u062a\u0623\u0643\u064a\u062f \u0639\u0628\u0631 {channel}.",
    "en": "It is booked: an advisor will call you back {when}. You will get the confirmation by {channel}.",
}
_CONFIRMED_NO_NOTIF = {
    "fr": "C'est not\u00e9 : un conseiller vous rappelle {when}.",
    "ar": "\u062a\u0645 \u0627\u0644\u062a\u0633\u062c\u064a\u0644: \u0633\u064a\u062a\u0635\u0644 \u0628\u0643 \u0645\u0633\u062a\u0634\u0627\u0631 {when}.",
    "en": "It is booked: an advisor will call you back {when}.",
}
_FAILED = {
    "fr": "Je n'ai pas pu enregistrer le rappel. Rien n'a \u00e9t\u00e9 programm\u00e9, vous pouvez nous rappeler quand vous voulez.",
    "ar": "\u0644\u0645 \u0623\u062a\u0645\u0643\u0646 \u0645\u0646 \u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u0645\u0648\u0639\u062f. \u0644\u0645 \u064a\u062a\u0645 \u062d\u062c\u0632 \u0623\u064a \u0634\u064a\u0621.",
    "en": "I could not register the callback. Nothing was scheduled; you can call us back any time.",
}
_CHANNEL = {
    "whatsapp": {"fr": "WhatsApp", "ar": "\u0648\u0627\u062a\u0633\u0627\u0628", "en": "WhatsApp"},
    "email": {"fr": "e-mail", "ar": "\u0627\u0644\u0628\u0631\u064a\u062f \u0627\u0644\u0625\u0644\u0643\u062a\u0631\u0648\u0646\u064a", "en": "email"},
    "sms": {"fr": "SMS", "ar": "\u0631\u0633\u0627\u0644\u0629 \u0642\u0635\u064a\u0631\u0629", "en": "SMS"},
}
_JOIN = {"fr": " et ", "ar": " \u0648 ", "en": " and "}

_NOT_THAT_TIME = {
    "fr": "Ce moment-la n'est pas possible. ",
    "en": "That time is not possible. ",
    "ar": "That time is not possible. ",
}
_CLOSED = {
    "fr": "Nous ne travaillons pas a ce moment-la. ",
    "en": "We are not working at that time. ",
    "ar": "We are not working at that time. ",
}
_FULL = {
    "fr": "Ce creneau est deja complet. ",
    "en": "That slot is already full. ",
    "ar": "That slot is already full. ",
}
_TOO_SOON = {
    "fr": "C'est trop proche, il nous faut un peu de temps. ",
    "en": "That is too soon, we need a little time. ",
    "ar": "That is too soon, we need a little time. ",
}
_WHAT_SUITS = {
    "fr": "Est-ce que l'un de ces horaires vous conviendrait ?",
    "en": "Would one of these times suit you?",
    "ar": "Would one of these times suit you?",
}

BUSINESS_TZ = ZoneInfo(os.getenv("CALLBACK_TIMEZONE", "Africa/Tunis"))

_DAY_WORDS = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
    "samedi": 5, "dimanche": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
}
_PART_OF_DAY = {"matin": 9, "morning": 9, "apres-midi": 15, "afternoon": 15,
                "midi": 12, "noon": 12, "soir": 17, "evening": 17}


def parse_requested_time(text: str, now: datetime | None = None) -> str | None:
    """Turn what the caller said into one ISO instant, or None when it is genuinely ambiguous.

    Deterministic on purpose. A model asked to "understand the date" will confidently produce a
    Thursday that does not exist, and the caller will be waiting for a call nobody scheduled.
    Returning None is the safe failure: the agent then simply offers the next real slots.
    """
    if not text:
        return None
    raw = text.strip().lower()
    now = (now or datetime.now(BUSINESS_TZ)).astimezone(BUSINESS_TZ)

    day: _date | None = None
    if "apres demain" in raw or "apres-demain" in raw or "day after tomorrow" in raw:
        day = (now + timedelta(days=2)).date()
    elif "demain" in raw or "tomorrow" in raw:
        day = (now + timedelta(days=1)).date()
    elif "aujourd" in raw or "today" in raw:
        day = now.date()

    if day is None:
        explicit = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", raw)
        if explicit:
            d, m, y = explicit.groups()
            year = int(y) if y else now.year
            if year < 100:
                year += 2000
            try:
                day = _date(year, int(m), int(d))
            except ValueError:
                return None

    if day is None:
        for word, weekday in _DAY_WORDS.items():
            if word in raw:
                ahead = (weekday - now.weekday()) % 7 or 7
                day = (now + timedelta(days=ahead)).date()
                break

    hour, minute = None, 0
    clock = re.search(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?", raw)
    if clock:
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
    else:
        bare = re.search(r"\b(\d{1,2})\s*(?:heures?|hours?|o'clock)\b", raw)
        if bare:
            hour = int(bare.group(1))
    if hour is not None and hour < 8 and ("soir" in raw or "pm" in raw or "apres" in raw):
        hour += 12
    if hour is None:
        for word, default_hour in _PART_OF_DAY.items():
            if word in raw:
                hour = default_hour
                break

    if day is None and hour is None:
        return None
    if day is None:
        day = now.date() if (hour or 0) > now.hour else (now + timedelta(days=1)).date()
    if hour is None:
        hour = 9
    if not 0 <= hour <= 23:
        return None
    return datetime(day.year, day.month, day.day, hour, minute,
                    tzinfo=BUSINESS_TZ).isoformat()


def _lang(session) -> str:
    """Caller language with a French default; never raises."""
    value = getattr(getattr(session, "userdata", None), "language", "fr") or "fr"
    return value if value in _OFFER_ONE else "fr"


def _spoken(slot_start: str, language: str) -> str:
    """Human phrasing of a slot, e.g. 'mardi a 9h30'. Falls back to the raw ISO string
    rather than guessing, because a wrong appointment is worse than an awkward one."""
    try:
        when = datetime.fromisoformat(slot_start)
    except ValueError:
        return slot_start
    day = _WEEKDAYS.get(language, _WEEKDAYS["fr"])[when.weekday()]
    if language == "fr":
        minute = "" if when.minute == 0 else f"{when.minute:02d}"
        return f"{day} \u00e0 {when.hour}h{minute}"
    if language == "ar":
        return f"{day} \u0627\u0644\u0633\u0627\u0639\u0629 {when.hour}:{when.minute:02d}"
    return f"{day} at {when.hour}:{when.minute:02d}"


class CallbackScheduleTask(AgentTask[bool]):
    """Offer real slots, negotiate, book, notify. Returns True only if a row was written."""

    def __init__(self, reason: str = "", customer_context=None) -> None:
        super().__init__(
            instructions=(
                "You are arranging a callback. Offer the slots you are given, accept a "
                "counter-proposal from the caller, and call accept_slot as soon as they agree "
                "on one. Never invent a time that was not offered. If they refuse a callback, "
                "call decline_callback. "
                "When the caller names a day or a time, always call request_other_time with "
                "their exact words. Never judge availability yourself and never invent a time: "
                "only offer times the tools returned. If a time is refused, say briefly why "
                "and immediately offer the alternatives you were given."
            )
        )
        self._reason = reason
        self._customer = customer_context
        self._slots: list[dict] = []
        self._done = False
        self._watchdog: asyncio.Task | None = None

    # -- lifecycle ---------------------------------------------------------------

    async def on_enter(self) -> None:
        language = _lang(self.session)
        self._slots = await get_callback_client().free_slots()
        if not self._slots:
            # Being honest here is the whole point: the previous code booked now+24h even when
            # no advisor was on call.
            await self.session.say(_NO_SLOT[language])
            await self._finish(False)
            return

        first = _spoken(self._slots[0]["slot_start"], language)
        if len(self._slots) > 1:
            second = _spoken(self._slots[1]["slot_start"], language)
            await self.session.say(_OFFER_TWO[language].format(first=first, second=second))
        else:
            await self.session.say(_OFFER_ONE[language].format(first=first))
        self._arm()

    def _arm(self) -> None:
        """Re-arm the idle watchdog. Bounding silence, not the negotiation, is what stops the
        task from ending while the caller is still choosing a time."""
        if self._watchdog is not None:
            self._watchdog.cancel()
        self._watchdog = asyncio.create_task(self._idle_timeout())

    async def _idle_timeout(self) -> None:
        try:
            await asyncio.sleep(IDLE_DEADLINE_S)
        except asyncio.CancelledError:
            return
        if self._done:
            return
        logger.info("callback negotiation idle -> no callback scheduled")
        await self.session.say(_FAILED[_lang(self.session)])
        await self._finish(False)

    async def _finish(self, outcome: bool) -> None:
        if self._done:
            return
        self._done = True
        if self._watchdog is not None:
            self._watchdog.cancel()
        self.complete(outcome)

    # -- tools -------------------------------------------------------------------

    @function_tool()
    async def accept_slot(self, context: RunContext, slot_start: str = "") -> str:
        """Book the slot the caller just agreed to.

        Pass the slot_start value exactly as it was offered to you. If the caller agreed to
        the first proposal, pass the first one.
        """
        self._arm()
        if self._done:
            return "The callback step is already finished; do not book again."

        language = _lang(self.session)
        chosen = self._match(slot_start)
        if chosen is None:
            return self._offer_again(language)

        user_data = self.session.userdata
        booked = await get_callback_client().reserve(
            chosen,
            customer_id=getattr(self._customer, "customer_id", None),
            subscription_id=getattr(self._customer, "subscription_id", None),
            session_id=getattr(user_data, "session_id", None),
            preferred_window=_spoken(chosen, language),
            reason=self._reason,
        )
        if booked is None:
            # Someone else took the slot between the offer and the answer: re-read and re-offer
            # instead of failing the whole request.
            self._slots = await get_callback_client().free_slots()
            if not self._slots:
                await self.session.say(_NO_SLOT[language])
                await self._finish(False)
                return "No slot left; the caller has been told."
            return self._offer_again(language, alternatives=True)

        spoken = _spoken(chosen, language)
        user_data.callback_requested = True
        user_data.callback_when = chosen

        channels = await self._notify(language, spoken)
        if channels:
            label = _JOIN[language].join(_CHANNEL[c][language] for c in channels)
            await self.session.say(_CONFIRMED[language].format(when=spoken, channel=label))
        else:
            # The appointment is real even when the confirmation message could not go out;
            # promising a message that never arrives would be a second broken promise.
            await self.session.say(_CONFIRMED_NO_NOTIF[language].format(when=spoken))
        await self._finish(True)
        return "Callback booked and confirmed to the caller."

    @function_tool()
    async def request_other_time(self, context: RunContext, preferred_time: str) -> str:
        """Called when the caller proposes a time in their own words.

        Args:
            preferred_time: exactly what the caller said, e.g. "jeudi vers 14h", "le 31/07".
        """
        self._arm()
        if self._done:
            return "The callback step is already finished."

        lang = _lang(self.session)
        reason_map = {"closed": _CLOSED, "full": _FULL, "too_soon": _TOO_SOON}

        requested = parse_requested_time(preferred_time)
        if requested is None:
            # Not understood is not a failure: fall back to offering what genuinely exists.
            self._slots = await get_callback_client().free_slots(days=2, limit=2)
            return self._offer_again(lang)

        verdict = await get_callback_client().check_time(requested)

        if verdict.get("available"):
            # Book the instant the API confirmed, never the one we parsed.
            return await self.accept_slot(context, verdict["slot_start"])

        self._slots = list(verdict.get("alternatives") or [])
        prefix = reason_map.get(verdict.get("reason", ""), _NOT_THAT_TIME)[lang]
        if not self._slots:
            return prefix + _NO_SLOT[lang]
        return prefix + self._offer_again(lang) + " " + _WHAT_SUITS[lang]

    @function_tool()
    async def decline_callback(self, context: RunContext) -> str:
        """The caller does not want a callback."""
        await self._finish(False)
        return "No callback wanted; continue the conversation normally."

    # -- helpers -----------------------------------------------------------------

    def _match(self, slot_start: str) -> str | None:
        """Only a slot that was actually offered can be booked: this is the guard against a
        hallucinated appointment."""
        wanted = (slot_start or "").strip()
        for slot in self._slots:
            if slot["slot_start"] == wanted:
                return wanted
        return self._slots[0]["slot_start"] if len(self._slots) == 1 else None

    def _sorted_by_hint(self, preferred_time: str) -> list[dict]:
        """Re-rank free slots around an hour heard from the caller ('plutot vers 15h')."""
        digits = re.findall(r"\d{1,2}", preferred_time or "")
        if not digits:
            return self._slots
        target = int(digits[0])
        if not 0 <= target <= 23:
            return self._slots

        def distance(slot: dict) -> int:
            try:
                return abs(datetime.fromisoformat(slot["slot_start"]).hour - target)
            except ValueError:
                return 99

        return sorted(self._slots, key=distance)

    def _offer_again(self, language: str, alternatives: bool = False) -> str:
        """Re-state up to two slots as a tool result so the model speaks them verbatim."""
        if not self._slots:
            return "No slot is free; tell the caller honestly and call decline_callback."
        first = _spoken(self._slots[0]["slot_start"], language)
        second = _spoken(self._slots[1]["slot_start"], language) if len(self._slots) > 1 else first
        template = _ALTERNATIVES if alternatives else _OFFER_TWO
        sentence = template[language].format(first=first, second=second)
        offered = ", ".join(s["slot_start"] for s in self._slots[:2])
        return f"Say exactly: {sentence} -- bookable slot_start values: {offered}"

    async def _notify(self, language: str, spoken: str) -> list[str]:
        """Confirm on every reachable channel. Returns what actually went out."""
        customer_id = getattr(self._customer, "customer_id", None)
        if not customer_id:
            logger.warning("callback booked without a customer_id: no written confirmation")
            return []
        return await get_notification_client().notify_all_available(
            customer_id, "callback_scheduled", language, {"when": spoken}
        )
