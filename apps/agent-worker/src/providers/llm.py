"""LLM builder: OpenAI primary + Google Gemini fallback via llm.FallbackAdapter.

[verify] model id strings churn; they are env-driven and confirmed against
docs.livekit.io/agents/models at build time.
"""
from __future__ import annotations

from livekit.agents import llm as llm_module
from livekit.plugins import google, openai

from providers._resilience import chaos_model


def build_llm(primary_model: str, fallback_model: str, break_primary: bool = False):
    """Return an LLM FallbackAdapter (OpenAI primary, Gemini fallback)."""
    primary = openai.LLM(model=chaos_model(primary_model, break_primary))
    fallback = google.LLM(model=fallback_model)
    return llm_module.FallbackAdapter([primary, fallback])