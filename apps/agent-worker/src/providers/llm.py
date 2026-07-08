"""LLM builder: configurable provider chain with OpenAI/Gemini primary toggle.

When ``OPENAI_ENABLED=true`` the chain is:
  1. openai.LLM  — GPT-4o-mini      [primary, requires OPENAI_API_KEY]
  2. google.LLM  — Gemini 2.5 Flash  [first fallback, requires GOOGLE_API_KEY]
  3. NvidiaLLM   — NVIDIA NIM        [fallback, skipped if NVIDIA_API_KEY absent]
  4. GroqLLM     — Groq (llama)      [fallback, skipped if GROQ_API_KEY absent]

When ``OPENAI_ENABLED=false`` OpenAI is skipped entirely:
  1. google.LLM  — Gemini 2.5 Flash  [primary, GOOGLE_API_KEY required]
  2. NvidiaLLM   — NVIDIA NIM        [fallback, skipped if NVIDIA_API_KEY absent]
  3. GroqLLM     — Groq (llama)      [fallback, skipped if GROQ_API_KEY absent]

[verify] model id strings churn; they are env-driven and confirmed against
docs.livekit.io/agents/models at build time.
"""
from __future__ import annotations

import os

from livekit.agents import llm as llm_module
from livekit.plugins import google, openai

from providers._resilience import chaos_model
from providers.groq_adapter import GroqLLM
from providers.nvidia_adapter import NvidiaLLM


def build_llm(primary_model: str, fallback_model: str, break_primary: bool = False,
              openai_enabled: bool = False):
    """Return an LLM FallbackAdapter with the configured provider chain.

    The chain is built dynamically based on which API keys are present.
    Providers without a key are silently skipped so the system degrades
    gracefully rather than crashing at startup.

    When ``openai_enabled`` is True OpenAI becomes the primary provider and
    Gemini is the first fallback. When False OpenAI is skipped entirely and
    Gemini serves as primary.

    Args:
        primary_model:  Gemini model ID (env: LLM_PRIMARY_MODEL).
        fallback_model: OpenAI model ID  (env: LLM_FALLBACK_MODEL).
        break_primary:  Chaos toggle — substitutes the invalid model id so the
                        primary intentionally fails and the fallback takes over.
        openai_enabled: When True, OpenAI is the primary and Gemini is the
                        first fallback. When False, OpenAI is skipped.
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    providers: list = []

    if openai_enabled and openai_key:
        # --- Primary: OpenAI GPT ---
        providers.append(openai.LLM(model=chaos_model(fallback_model, break_primary)))

        # --- First fallback: Google Gemini 2.5 Flash ---
        providers.append(google.LLM(model=primary_model))
    else:
        # --- Primary: Google Gemini 2.5 Flash ---
        providers.append(google.LLM(model=chaos_model(primary_model, break_primary)))

    # --- Fallback: NVIDIA NIM (optional) ---
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        nvidia_timeout = float(os.getenv("NVIDIA_TIMEOUT_S", "45.0"))
        providers.append(NvidiaLLM(api_key=nvidia_key, model=nvidia_model, timeout=nvidia_timeout))

    # --- Fallback: Groq (optional) ---
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        groq_timeout = float(os.getenv("GROQ_TIMEOUT_S", "30.0"))
        providers.append(GroqLLM(api_key=groq_key, model=groq_model, timeout=groq_timeout))

    return llm_module.FallbackAdapter(providers, attempt_timeout=12.0)