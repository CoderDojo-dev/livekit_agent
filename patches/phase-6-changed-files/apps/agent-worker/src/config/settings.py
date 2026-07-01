"""Twelve-Factor settings: everything via environment, nothing hardcoded.

This module holds configuration values only. It imports no vendor plugin: provider
construction (including noise cancellation) lives behind the providers/ boundary.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker configuration loaded from the environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- LiveKit transport (self-hosted) ---
    livekit_url: str = Field("ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_api_key: str = Field("devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field("devsecret_change_me", alias="LIVEKIT_API_SECRET")

    # --- Language scope / spike session language ---
    supported_languages: str = Field("fr,ar,en", alias="SUPPORTED_LANGUAGES")
    default_language: str = Field("fr", alias="DEFAULT_LANGUAGE")
    session_language: str = Field("fr", alias="SESSION_LANGUAGE")
    session_caller_msisdn: str = Field("", alias="SESSION_CALLER_MSISDN")

    # --- STT primary (Deepgram) ---
    stt_model: str = Field("nova-3", alias="STT_MODEL")
    # --- TTS primary (ElevenLabs Flash v2.5) ---
    tts_model: str = Field("eleven_flash_v2_5", alias="TTS_MODEL")
    eleven_voice_id: str = Field("EXAVITQu4vr4xnSDxMaL", alias="ELEVEN_VOICE_ID")
    # --- LLM chain (OpenAI primary, Gemini fallback) [verify model ids] ---
    llm_primary_model: str = Field("gpt-4.1-mini", alias="LLM_PRIMARY_MODEL")
    llm_fallback_model: str = Field("gemini-2.0-flash", alias="LLM_FALLBACK_MODEL")

    # --- VAD / turn detection / latency ---
    vad_min_silence: float = Field(0.25, alias="VAD_MIN_SILENCE")
    preemptive_generation: bool = Field(True, alias="PREEMPTIVE_GENERATION")
    noise_cancellation: bool = Field(False, alias="NOISE_CANCELLATION")

    # --- Decision -> Policy façade ---
    decision_confidence_threshold: float = Field(0.5, alias="DECISION_CONFIDENCE_THRESHOLD")

    # --- Resilience chaos toggles (cookbook section 16): break a primary on purpose ---
    chaos_break_stt: bool = Field(False, alias="CHAOS_BREAK_STT")
    chaos_break_llm: bool = Field(False, alias="CHAOS_BREAK_LLM")
    chaos_break_tts: bool = Field(False, alias="CHAOS_BREAK_TTS")

    # --- Domain service URLs ---
    context_service_url: str = Field("http://localhost:8101", alias="CONTEXT_SERVICE_URL")
    decision_service_url: str = Field("http://localhost:8103", alias="DECISION_SERVICE_URL")
    policy_service_url: str = Field("http://localhost:8104", alias="POLICY_SERVICE_URL")
    execution_service_url: str = Field("http://localhost:8105", alias="EXECUTION_SERVICE_URL")
    notification_service_url: str = Field("http://localhost:8106", alias="NOTIFICATION_SERVICE_URL")
    knowledge_glpi_mcp_url: str = Field("http://localhost:8201/mcp", alias="KNOWLEDGE_GLPI_MCP_URL")

    @property
    def languages(self) -> list[str]:
        """Parsed supported-language list."""
        return [item.strip() for item in self.supported_languages.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()