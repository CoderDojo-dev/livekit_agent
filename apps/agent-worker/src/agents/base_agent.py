"""Shared base persona: per-turn sentiment + proactive de-escalation + conversation logging.

on_user_turn_completed runs after the caller's turn and BEFORE the reply. It scores the turn
(updating frustration), records the turn + sentiment to the durable conversation log (off the
voice path), and injects a transient de-escalation note when frustration is high (cookbook 12).
"""
from __future__ import annotations

import logging

from conversation.writer import sentiment_label
from livekit.agents import Agent
from livekit.agents.types import NotGivenOr
from sentiment.sentiment_scorer import get_sentiment_scorer
from tools.session_flow_tools import end_conversation, switch_spoken_language

logger = logging.getLogger(__name__)

# Shared closing protocol appended to every persona's instructions so ending a
# call behaves identically no matter which specialist is active.
CLOSING_PROTOCOL = (
    "\n\nEnding the call: when the caller's need is fully handled — information "
    "delivered, a ticket created, an issue escalated, a callback scheduled, or "
    "the caller signals they are finished — first ask, in the caller's language, "
    "whether there is anything else you can help with. If they need more, "
    "continue normally. Only once the caller clearly has nothing else, or clearly "
    "wants to leave or says goodbye, call end_conversation to close the call. "
    "Judge this from the caller's intent, not from a fixed list of keywords. "
    "Never call end_conversation while the caller still needs help, and never end "
    "without first confirming there is nothing else. When you call "
    "end_conversation, do not also speak a goodbye yourself — the tool delivers "
    "the farewell."
)

# Resolves the contradiction between the per-persona "Never switch to another
# language" lock and the auto-injected switch_spoken_language tool: the lock
# still prevents self-initiated drift, but an EXPLICIT caller request is allowed.
LANGUAGE_SWITCH_POLICY = (
    "\n\nLanguage: keep speaking your fixed language and never drift on your own. "
    "The only exception overriding any 'never switch language' rule above: if the "
    "caller EXPLICITLY asks to continue in French, Arabic, or English, call "
    "switch_spoken_language with that language code, then continue in it."
)

NO_DEAD_END_MANDATE = (
    "\n\nRouting mandate (you MUST follow this):\n"
    "- If the caller asks about their BALANCE, INVOICE, PAYMENT, or DEFERRAL, "
    "call route_to_billing immediately.\n"
    "- If the caller asks about their PLAN, RECHARGE, ROAMING, or PHONE LINE, "
    "call route_to_account_services immediately.\n"
    "- If the caller has a SIM, NETWORK, or CONNECTIVITY problem, "
    "call route_to_technical immediately.\n"
    "- If the request is ambiguous, call request_clarification.\n"
    "- NEVER tell the caller to call a different department or number yourself. "
    "Use the route_* tool. If none of the above fits, call escalate_to_manager.\n"
    "- The route_* tools transfer the caller to the right specialist; after calling "
    "one you will NOT speak again, so do not also say goodbye yourself."
)


def merge_instructions(persona_core: str, tts_provided: bool = True) -> str:
    """Assemble the full instruction block for a persona agent.

    Every agent gets: its own core instructions, the shared NO_DEAD_END_MANDATE,
    CLOSING_PROTOCOL, and LANGUAGE_SWITCH_POLICY — in that order, deduplicated.
    tts_provided controls whether the 'speak only in X' language lock is added
    below NO_DEAD_END_MANDATE.
    """
    parts = [persona_core, NO_DEAD_END_MANDATE, CLOSING_PROTOCOL, LANGUAGE_SWITCH_POLICY]
    # A TTS-locked persona gets a second reminder not to switch
    if tts_provided:
        parts.append("\n\nIMPORTANT: You MUST speak ONLY in the language already specified above. Never switch.")
    return "\n".join(parts)

# Phase 8.1: knowledge-answer abstention rule. Appended ONLY to the personas that call
# knowledge_search (triage, billing, technical). Forces the agent to ground in retrieved
# passages and say "Je n'ai pas cette information." when they don't directly answer, so a
# residual retrieval leak (see Phase 8 report §6) cannot become a hallucinated answer.
KNOWLEDGE_ABSTENTION_RULE = (
    "When you use the knowledge_search tool, GROUND your answer strictly in the returned passages: "
    "never guess or add facts they do not contain, and if they do not directly answer the question, "
    "reply in French: \"Je n'ai pas cette information.\"\n"
    "But you are TALKING on a phone call, not reading a document. Never read a passage aloud "
    "verbatim, and never use numbered or bulleted lists (no \"1- 2- 3-\"), headings, or long "
    "paragraphs. Instead, answer the way a real advisor speaks out loud: ONE or two short, natural "
    "sentences carrying only the essential point the caller needs, in their language. Do not say "
    "source codes, file names, or URLs aloud. Then, in the same breath, briefly offer more if they "
    "want it (e.g. whether they'd like the exact steps or more detail). ONLY if the caller asks for "
    "more do you give further detail or the concrete steps - and even then keep it spoken: short, "
    "one point at a time, conversational, never a read-out list or a wall of text."
)


def _extract_text(message) -> str:
    """Best-effort extraction of the user's text from a ChatMessage (content may be str or list)."""
    text_content = getattr(message, "text_content", None)
    if isinstance(text_content, str):
        return text_content
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part for part in content if isinstance(part, str))
    return ""


class BaseTelecomAgent(Agent):
    """Every persona inherits this to share the sentiment/escalation + logging observer."""

    def __init__(self, *, instructions: str, tools=None, **kwargs) -> None:
        """Give every persona the shared closing protocol + end_conversation tool.

        Personas keep passing their own instructions/tools; this centralizes the
        graceful-end capability so it stays consistent and never drifts per persona.
        """
        merged_tools = list(tools or [])
        if end_conversation not in merged_tools:
            merged_tools.append(end_conversation)
        if switch_spoken_language not in merged_tools:
            merged_tools.append(switch_spoken_language)
        language = kwargs.pop("language", None)
        super().__init__(
            instructions=instructions,
            tools=merged_tools,
            **kwargs,
        )
        if language:
            _LANG_MAP = {"fr": "French", "ar": "Arabic", "en": "English"}
            selected = language if language in _LANG_MAP else "fr"
            self._language = selected
            self._lang_name = _LANG_MAP[selected]

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Score the turn, log it (off-path), and inject a de-escalation note when frustration is high."""
        user_data = getattr(self.session, "userdata", None)
        if user_data is None:
            return

        # Patch #5 — le compteur de clarifications doit mesurer les deferrals
        # CONSÉCUTIFS sur le sujet courant, pas le total de l'appel. Si le client
        # répond à une clarification qu'on vient de poser, on conserve le streak ;
        # sinon il est passé à un tour normalement traité -> on réinitialise.
        if getattr(user_data, "_clarification_pending", False):
            user_data._clarification_pending = False
        else:
            user_data.clarification_attempts = 0

        transcript = _extract_text(new_message).strip()
        if transcript:
            logger.info("caller_transcript=%s", transcript)
            try:
                get_sentiment_scorer().score(transcript, user_data)
            except Exception as exc:
                logger.debug("sentiment scoring skipped: %s", exc)

            writer = getattr(user_data, "conversation_writer", None)
            if writer is not None:
                score = user_data.sentiment_history[-1] if getattr(user_data, "sentiment_history", None) else 0.0
                writer.record_turn(
                    speaker="caller", text=transcript,
                    active_agent=type(self).__name__, language=getattr(user_data, "language", None),
                )
                writer.record_sentiment(score=score, label=sentiment_label(score))

        if getattr(user_data, "should_offer_escalation", False):
            try:
                lang = getattr(self, "_lang_name", None)
                if not lang and user_data is not None:
                    lang_code = getattr(user_data, "language", "fr")
                    val = getattr(lang_code, "value", lang_code)
                    _MAP = {"fr": "French", "ar": "Arabic", "en": "English"}
                    lang = _MAP.get(str(val).lower().strip()[:2], "French")
                lang = lang or "French"
                note = (
                    "The caller appears repeatedly frustrated. In your next reply, strictly in "
                    f"{lang} ONLY, sincerely acknowledge their frustration, stay brief and calm, "
                    "and proactively offer to connect them with a human specialist. If they agree, "
                    "call escalate_to_manager. Never switch language."
                )
                turn_ctx.add_message(role="system", content=note)
                logger.info("frustration high -> injected proactive de-escalation note (%s)", lang)
            except Exception as exc:
                logger.debug("frustration injection skipped: %s", exc)
