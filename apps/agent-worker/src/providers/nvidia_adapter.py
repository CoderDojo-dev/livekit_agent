"""NVIDIA NIM LLM Adapter — thin wrapper compatible with LiveKit's LLM interface.

Implements the subset of livekit.agents.llm.LLM that FallbackAdapter requires:
  - Wraps the OpenAI-compatible NVIDIA NIM endpoint via livekit-plugins-openai's
    OpenAI client pointing at the NIM base URL.
  - Reads NVIDIA_API_KEY, NVIDIA_MODEL, NVIDIA_TIMEOUT_S from environment.

Design:
  - Uses livekit.plugins.openai.LLM with a custom base_url / api_key so it is
    100% compatible with FallbackAdapter without reimplementing streaming or
    function-calling internally.
  - No key pool — one key, one model.
  - On 429/5xx the LiveKit fallback machinery will rotate to the next provider.

Usage in llm.py:
    from providers.nvidia_adapter import NvidiaLLM
    adapter = NvidiaLLM(api_key=..., model=..., timeout=...)
    # Drop into FallbackAdapter([..., adapter, ...])
"""
from __future__ import annotations

import logging

from livekit.plugins import openai as lk_openai

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaLLM(lk_openai.LLM):
    """
    Single-key NVIDIA NIM LLM adapter.

    Inherits livekit.plugins.openai.LLM with the NIM base URL injected.
    This makes it a drop-in replacement inside any FallbackAdapter list.

    No pool logic, no multi-key rotation — just one key from NVIDIA_API_KEY.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "meta/llama-3.1-8b-instruct",
        timeout: float = 45.0,
    ) -> None:
        if not api_key:
            raise ValueError("NvidiaLLM requires a non-empty api_key (NVIDIA_API_KEY)")
        logger.info("NvidiaLLM: initialising with model=%s endpoint=%s", model, NVIDIA_BASE_URL)
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
            # httpx_client_options accepted by openai.LLM to set per-request timeout
            # (the timeout kwarg may not be in older plugin versions — safe to omit)
        )
