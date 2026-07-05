"""Groq LLM Adapter — thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the Groq OpenAI-compatible endpoint via livekit-plugins-openai's
    OpenAI client pointing at Groq's base URL.
  - Reads GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with Groq's base_url / api_key injected,
    identical pattern to NvidiaLLM — no new streaming/function-call logic needed.
  - No key pool — one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.

Usage in llm.py:
    from providers.groq_adapter import GroqLLM
    adapter = GroqLLM(api_key=..., model=..., timeout=...)
    # Drop into FallbackAdapter([..., adapter])
"""
from __future__ import annotations

import logging

import httpx
from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLM(lk_openai.LLM):
    """
    Single-key Groq LLM adapter.

    Inherits livekit.plugins.openai.LLM with the Groq base URL injected.
    Drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation — just one key from GROQ_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "llama-3.1-8b-instant",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("GroqLLM requires a non-empty api_key (GROQ_API_KEY)")
        logger.info("GroqLLM: init model=%s endpoint=%s timeout=%.0fs",
                    model, GROQ_BASE_URL, timeout)
        super().__init__(model=model, api_key=api_key, base_url=GROQ_BASE_URL,
                         timeout=httpx.Timeout(timeout, connect=10.0))
